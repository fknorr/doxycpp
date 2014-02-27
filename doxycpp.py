#!/usr/bin/env python3


# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


    
import hashlib, copy, sys, locale, os
from lxml import etree


config = { "show_protected": True, "show_private": False }



locale = { "dirs": "subdirectories", "dir": "Directory", "defines": "preprocessor macros", \
          "group": "module", "groups": "modules", "page": "special page", \
          "pages": "special pages", "headers": "header files", "alindex": "alphabetical index" }
      
'''
locale = { "dir": "Verzeichnis", "dirs": "Unterverzeichnisse", "define": "Präprozessormakro", \
           "defines": "Präprozessormakros", "group": "Modul", "groups": "Module", \
           "page": "Seite", "pages": "Seiten", "file": "Datei", "files": "Dateien", \
           "type": "Datentyp", "types": "Datentypen", "function": "Funktion", \
           "functions": "Funktionen", "public": "Öffentliche", "variables": "Variablen", \
           "namespace": "Namensraum", "namespaces": "Namensräume", "class": "Klasse", \
           "classes": "Klassen", "struct": "Struktur", "structs": "Strukturen", \
           "enum": "Aufzählung", "enums": "Aufzählungen" }
'''

def localize(spec):
    return locale[spec] if spec in locale else spec


if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print("DoxyC++ Doxygen XML to HTML postprocessor version 1.0.3\n"
        + "(C) 2014, Fabian Knorr <https://github.com/fknorr/doxycpp>\n\n"
        + "DoxyC++ is free software: you can redistribute it and/or modify it under\n"
        + "the terms of the GNU General Public License as published by the Free Software\n"
        + "Foundation, either version 3 of the License, or (at your option) any later\n"
        + "version.", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 2 or (len(sys.argv) > 1 and sys.argv[1] == "--help"):
    print("Syntax: " + sys.argv[0] + " <output directory>\n"
        + "        " + sys.argv[0] + " --help     Display this help\n"
        + "        " + sys.argv[0] + " --version  Display version information\n\n"
        + "DoxyC++ will read XML files from the current directory.", file=sys.stderr)
    sys.exit(1)


output_dir = sys.argv[1]


# A Declaration, extracted from XML. This is paritally resolved information and still contains
# some XML tags.
class Declaration:
    def __init__(self, _doxygen_id):
        # The containing Declaration instance
        self.parent = None
        
        # The doxygen ID, as mapped by the declarations dict
        self.doxygen_id = _doxygen_id

        # The visiblity inside "parent", e.g. "public" or "private"
        self.visibility = "public"
        
        # Whether the declaration is static within "parent"
        self.is_static = False
        
        # The kind of declaration, e.g. "typedef", "struct", or "function"
        self.kind = "none"
        
        # The (short) name of the declaration inside its scope, may initially
        # contain scoping information but will be removed later
        self.name = ""

        # The full, scoped name in the global namespace
        self.full_name = ""

        # The @brief-description
        self.brief_description = None

        # Doxygen IDs of all direct (non-inherited) member
        self.members = set()

        # Doxygen IDs of all direct and inherited members
        self.all_members = set()

        # The declaration's relative URL, that is either a file name like "namespace-sde-b191.html"
        # or a file name with an anchor for an inlined definition
        # (like "namespace-sde-b191.html#typedef-sde-floatmax_t-896f")
        self.target_url = ""

        # The <a>nchor part of a URL if it is an inline_doc (e.g. "typedef-sde-floatmax_t-896f")
        self.target_url_anchor = ""

        # The XML <definition> tag usually containing the full declaration code
        self.definition = None

        # All XML <includes> tags in this declaration
        self.include_files = []

        # Whether the declared function is marked "inline"
        self.is_inline = False

        # Whether the declared function is marked "virtual"
        self.is_virtual = False

        # The XML <templateparamlist> tag associated with this declaration, if any
        self.template_params = None

        # The XML <initializer> tag of this declaration, if any
        self.initializer = None

        # The XML <type> tag of this declaration, i.e. the return type or variable type
        self.data_type = None

        # A list of XML <enumvalue> tags associated with this declaration
        self.enum_values = []

        # A list of XML <basecompoundref> tags
        self.inherits_from = []

        # Stores whether the documentation of this node will be included into it's parent's page
        # This is true e.g. for typedefs.
        self.inline_doc = False

        # The XML <detaileddescription> of this declaration
        self.detailed_description = None

        # Whether the node is just an arbitrary collections of objects and thus does
        # not participate in the scope hierarchy (e.g. file member listings)
        self.is_collection = False

        # The page title if this is a special page
        self.page_title = None

        # The XML <argstring> tag of the declared function (if any)
        self.parameters = None

        # Whether the declaration (e.g. a constructor) was declared "explicit
        self.is_explicit = False


# Maps weird Doxygen IDs (like "classfn_1_1definition__array_4") to Declaration instances
declarations = dict()



# Reads a <compounddef> or <memberdef> tag, updating "declarations"
#   xml_node: The XML node to read from
#   parent_decl: The Declaration object containing this declaratinon, or None.
#   kind: The kind of declaration, corresponding to Declaration.kind
def read_xml_memberdef(xml_node, parent_decl, kind):
    doxygen_id = xml_node.get("id")
    
    # Add itself to parent
    if parent_decl != None: 
        parent_decl.all_members.add(doxygen_id)
        parent_decl.members.add(doxygen_id)

    # The doxygen_id might already have been visited (who knows?)
    if not doxygen_id in declarations:  
        member = Declaration(doxygen_id)     
        declarations[doxygen_id] = member
        member.kind = kind 
        member.inline_doc = (kind == "typedef" or kind == "variable" or kind == "define")
        member.is_collection = (kind == "group" or kind == "page" or kind == "file")
        member.visibility = xml_node.get("prot")
        member.is_static = xml_node.get("static") == "yes"
        member.is_virtual = xml_node.get("virtual") == "yes"
        member.is_inline = xml_node.get("inline") == "yes"
        member.is_explicit = xml_node.get("explicit") == "yes"

        for e in xml_node.iterchildren(tag=etree.Element):
            if e.tag == "type": member.data_type = e
            elif e.tag == "title": member.page_title = e.text
            elif e.tag == "definition": member.definition = e
            elif e.tag == "argsstring": member.parameters = e
            elif e.tag == "name" or e.tag == "compoundname": member.name = e.text
            elif e.tag == "inbodydescription": member.ibdescr = e
            elif e.tag == "briefdescription": member.brief_description = e
            elif e.tag == "initializer": member.initializer = e
            elif e.tag == "includes": member.include_files.append(e)
            elif e.tag == "detaileddescription": member.detailed_description = e
            elif e.tag == "templateparamlist": member.template_params = e
            elif e.tag == "enumvalue": member.enum_values.append(e)
            elif e.tag == "basecompoundref": member.inherits_from.append(e)

            # "#define"d macros need to have their parameter list built manually
            elif e.tag == "param":
                for f in e.iterchildren(tag=etree.Element):
                    if kind == "define" and f.tag == "defname":
                        if member.parameters != None: member.parameters.text += ", "
                        else: 
                            member.parameters = etree.Element("argsstring")
                            member.parameters.text = "("
                        member.parameters.text += f.text
        if kind == "define" and member.parameters != None:
            member.parameters.text += ")"    
        return member
        
    else: return declarations[doxygen_id]



# Parse all .xml files in the current directory, updating "declarations"
for file_name in os.listdir():
    if len(file_name) > 3 and file_name[-4:] == ".xml" and os.path.isfile(file_name):
        xtree = etree.parse(file_name)
        # <compounddef>s contain <memberdef>s and <innerclass>es, which hold the main information
        compounds = xtree.xpath("/doxygen/compounddef")
        for xml_node in compounds: 
            delcaration = read_xml_memberdef(xml_node, None, xml_node.get("kind"))
            for child in xml_node.iterchildren(tag=etree.Element):
                if child.tag == "innerclass" or child.tag == "innerfile" or child.tag == "innerdir":
                    delcaration.members.add(child.get("refid"))
                    delcaration.all_members.add(child.get("refid"))
                elif child.tag == "sectiondef": 
                    for f in child.iterchildren(tag="memberdef"):
                        read_xml_memberdef(f, delcaration, f.get("kind"))
                elif child.tag == "listofallmembers" and not delcaration.is_collection:
                    for f in child.iterchildren(tag="member"):
                        delcaration.all_members.add(f.get("refid"))



# Takes an arbitrary string, removes all non-alnum and non-_ characters, concatenating it 
# with -, and adding a hash to avoid collisions
def urlify_string(string):
    result = ""
    # Collapse multiple non-[0-9a-zA-Z_]-characters into a single "-"
    last_was_special_char = False
    for char in string:
        if (((char >= '0' and char <= '9') or (char >= 'a' and char <= 'z')
                or (char >= 'A' and char <= 'Z') or char == '_')): 
            result += char.lower()
            last_was_special_char = False
        elif not last_was_special_char:
            result += '-'
            if char == '~': result += "not-"
            last_was_special_char = True
    # Ensure there's a "-" before the hash
    if not last_was_special_char: result += '-'
    result += hashlib.md5(bytearray(string, 'utf-8')).hexdigest()[0:4]
    return result



# Recursively traverses the "declarations" dictionary and updates the "parent" field of
# each declaration to point to the containing node
def build_hierarchy(parent_decl):
    if not parent_decl.is_collection: 
        for doxygen_id in parent_decl.members:
            if doxygen_id in declarations:
                member = declarations[doxygen_id]
                # One node will usually be visited multiple times, only update "parent" once
                if member.parent == None:
                    member.parent = parent_decl
                    build_hierarchy(declarations[doxygen_id])
                    # Member functions are usually available by including their classes header
                    if declarations[doxygen_id].include_files == []:
                        declarations[doxygen_id].include_files = parent_decl.include_files


# Maps fully scoped namespace names to their Declaration object.
# Needed to resolve nested namespace hierarchies, as they don't contain each other as members
namespaces = {}

# Stupidly try to build a hierarchy for every declaration (not as recursive as possible)
for doxygen_id, decl in declarations.items():
    # Add parents where a hierarchy exists in the XML
    build_hierarchy(decl)
    # Namespaces don't contain each other, remember their full names to resolve them later
    if decl.kind == "namespace":
        namespaces[decl.name] = doxygen_id



# Dummy node for the "Index" page
root = Declaration("root")
root.kind = "root"
root.name = ""

# Assign all orphaned nodes to "root" so they will appear on the index page.
# This applies for all global namespace members and preprocessor #defines.
for doxygen_id, decl in declarations.items(): 
    if decl.parent == None:
        new_parent = root
        # Resolve nested namespaces by their scoped name
        if decl.kind == "namespace" and "::" in decl.name:
            container = namespaces[decl.name[0:decl.name.rfind("::")]]
            if container and container in declarations:
                new_parent = declarations[container]
        decl.parent = new_parent
        new_parent.all_members.add(doxygen_id)



# Recursively postprocesses all "name" and "full_name" fields of every declaration.
# In the XML, some names include scope while others don't (I guess nobody checked the XML output
# for consistency). This function ensures "name" is scope-less while adding full scope prefixes
# to full_name based on the members/parent hierarchy built above.
def generate_names(decl):
    # Rename anonymous enums
    if len(decl.name) > 0 and decl.name[0] == '@':
        decl.name = "(anonymous)"

    if "::" in decl.name:
        # Find the last, not template-parameter-enclosed occurrence of "::"
        start = 0; level = 0; i=0
        for c in decl.name:
            if c == '<': level += 1
            elif c == '>': level -= 1
            elif c == ':' and level == 0: start = i+1
            i += 1
        decl.name = decl.name[start:]

    # Directory names should end in "/"
    if decl.kind == "dir": decl.name += "/"

    # Add scope prefixes for identifiers
    if decl.parent != None and decl.kind != "file" and decl.parent.full_name != "": 
        decl.full_name = decl.parent.full_name + "::" + decl.name
    # And simply concatenate directory names as they already end in "/"
    elif decl.parent != None: 
        decl.full_name = decl.parent.full_name + decl.name

    # Creates the canonical URL (without .html) for a declaration
    def make_page_url(decl):
        if decl.full_name != "":
            return decl.kind + "-" + urlify_string(decl.full_name)
        else:
            return "index"

    # Non-inline (i.e. integrated in their parent's page) declarations have an own url,
    # inline docs are identified by an <a>nchor inside their parent
    if not decl.inline_doc:
        decl.target_url = make_page_url(decl) + ".html"
    elif decl.parent.target_url != None: 
        decl.target_url_anchor = make_page_url(decl)
        decl.target_url = decl.parent.target_url + "#" + decl.target_url_anchor

    # Proceed recursively for all members
    if not decl.is_collection:
        for doxygen_id in decl.all_members:
            if doxygen_id in declarations:
                generate_names(declarations[doxygen_id])


# Recursively generate name and full_name fields
generate_names(root)
root.page_title = localize("index")
root.target_url = "index.html"

        
# Replaces template parameters in a string with '< ... >' for brief declarations and type names
# of variables
def collapse_templates(string, template_depth):
    if string == None: return None, template_depth
    result = ""
    skipped_something=False
    for char in string:
        if char == '<':
            template_depth += 1
            if template_depth == 1: result += char
        elif char == '>' and template_depth > 0: 
            template_depth -= 1
            if template_depth == 0:
                if skipped_something: result += " ... "
                result += char
        elif template_depth > 0: skipped_something = True
        else: result += char
    return result, template_depth

    
def to_html_abbrev(tree, dest, nolinks=False):
    depth = 0
    dest.text, depth = collapse_templates(tree.text, depth)
    length = len(dest.text) if dest.text != None else 0
    for e in tree.iterchildren(tag="ref"):
        a = etree.SubElement(dest, "a" if not nolinks else "span")
        if e.get("refid") in declarations and not nolinks: 
            a.set("href", declarations[e.get("refid")].target_url)
        a.text, depth = collapse_templates(e.text, depth)
        a.tail, depth = collapse_templates(e.tail, depth)
        if a.text != None: length += len(a.text) 
        if a.tail != None: length += len(a.tail)
    return length
    

def to_html(tree, dest, nolinks=False):
    length = [0]
    def addlen(s): 
        if s != None: length[0] += len(s)
    
    if dest.text == None: dest.text = ""
    if tree.text != None:
        dest.text += tree.text
        addlen(dest.text)
    for e in tree.iterchildren(tag=etree.Element):
        if e.tag == "ref":
            if not nolinks:
                a = etree.SubElement(dest, "a")
                if e.get("refid") and e.get("refid") in declarations and declarations[e.get("refid")].target_url != None:
                    a.set("href", declarations[e.get("refid")].target_url)
            else:
                a = etree.SubElement(dest, "span")
            a.text = e.text; addlen(e.text)
            a.tail = e.tail; addlen(e.tail)
        elif e.tag == "para":
            p = etree.SubElement(dest, "p")
            length[0] += to_html(e, p, nolinks)
            p.tail = e.tail
        elif e.tag == "linebreak":
            etree.SubElement(dest, "br").tail = e.tail
        elif e.tag == "simplesect":
            h4 = etree.SubElement(dest, "h4")
            if e.get("kind") != None and e.get("kind") == "return":
                h4.text = "Returns:"; addlen(h4.text)
            elif e.get("kind") != None and e.get("kind") == "see":
                h4.text = "See also:"; addlen(h4.text)
            else:
                xp = e.xpath("title")
                if len(xp) > 0:
                    h4.text = xp[0].text; addlen(h4.text)
            div = etree.SubElement(dest, "div")
            div.set("class", "par")
            length[0] += to_html(e, div)
        elif e.tag == "programlisting":
            code = etree.SubElement(dest, "div")
            code.set("class", "listing")
            first = True
            for line in e.iterchildren(tag="codeline"):
                if not first: etree.SubElement(code, "br")
                else: first = False
                #p = etree.SubElement(code, "span")
                length[0] += to_html(line, code)
        elif e.tag == "computeroutput":
            code = etree.SubElement(dest, "span")
            code.set("class", "tt")
            to_html(e, code)
            code.tail = e.tail
        elif e.tag == "highlight":
            span = etree.SubElement(dest, "span")
            span.set("class", "hl-" + e.get("class"))
            length[0] += to_html(e, span)          
            span.tail = e.tail
        elif e.tag == "sp": 
            span = etree.SubElement(dest, "span")
            span.text = "\xa0"; length[0] += 1
            span.tail = e.tail
        elif e.tag == "bold":
            span = etree.SubElement(dest, "strong")
            to_html(e, span)
            span.tail = e.tail
        elif e.tag == "italic":
            span = etree.SubElement(dest, "em")
            to_html(e, span)
            span.tail = e.tail
        elif e.tag == "table":
            table = etree.SubElement(dest, "table")
            table.set("class", "paramlist")
            for row in e.iterchildren(tag="row"):
                tr = etree.SubElement(table, "tr")
                first = True
                for col in row.iterchildren(tag="entry"):
                    td = etree.SubElement(tr, "thead" if col.get("thead") == "yes" else "td")
                    td.set("class", "paramname" if first else "paramdescr")
                    length[0] += to_html(col, td)
                    if first: first = False      
            table.tail = e.tail
        elif e.tag == "parameterlist":
            h4 = etree.SubElement(dest, "h4")
            if e.get("kind") == "exception": h4.text = "Exceptions:"
            elif e.get("kind") == "templateparam": h4.text = "Template parameters:"
            else: h4.text = "Parameters:"
            addlen(h4.text)
            div = etree.SubElement(dest, "div")
            div.set("class", "par")
            table = etree.SubElement(div, "table")
            table.set("class", "paramlist")
            for item in e.iterchildren(tag="parameteritem"):
                tr = etree.SubElement(table, "tr")
                td_name = etree.SubElement(tr, "td")
                td_name.set("class", "paramname")
                td_descr = etree.SubElement(tr, "td")
                td_descr.set("class", "paramdescr")
                xp = item.xpath("parameternamelist/parametername")
                if len(xp) > 0: length[0] += to_html(xp[0], td_name)
                xp = item.xpath("parameterdescription")
                if len(xp) > 0: length[0] += to_html(xp[0], td_descr)
        elif e.tag == "variablelist":
            table = etree.SubElement(dest, "ul")
            table.set("class", "varlist")
            li = None
            for item in e.iterchildren(tag=etree.Element):
                if item.tag == "varlistentry":
                    li = etree.SubElement(table, "li")
                    for term in item.iterchildren(tag="term"):
                        p = etree.SubElement(li, "p")
                        p.set("class", "head")
                        to_html(term, p)
                elif item.tag == "listitem" and li != None:
                    to_html(item, etree.SubElement(li, "p"))            
            
    return length[0]

    
def any_decl(decl, dest):
    dest.set("class", "decl")
    if decl.template_params != None:
        span = etree.SubElement(dest, "span")
        span.set("class", "template")
        span.text = "template <"
        comma = False
        for param in decl.template_params.iterchildren(tag=etree.Element):
            types = param.xpath("type")
            if len(types) > 0: 
                if comma: span2.tail = ", "
                else: comma = True; span.text += " "
                span2 = etree.SubElement(span, "span")
                to_html(types[0], span2)
                span2.tail = types[0].tail
            names = param.xpath("declname")
            if len(names) > 0:
                span.tail = " "
                span2 = etree.SubElement(span, "span")
                span2.text = names[0].text
                span2.tail = names[0].tail
        etree.SubElement(span, "span").text = ">"
        etree.SubElement(dest, "br")
    
    
def func_var_decl(decl, dest, nolinks=False, abbrev=False):
    any_decl(decl, dest)
    span = etree.SubElement(dest, "span")
    span.set("class", "specs")
    span.text = ""
    if decl.is_explicit: span.text += "explicit "
    if decl.is_static: span.text += "static "
    if decl.is_virtual: span.text += "virtual "
    length = len(span.text)
    span = etree.SubElement(dest, "span")
    span.set("class", "type")
    if decl.kind != "define":
        if not abbrev: length += to_html(decl.data_type, span, nolinks)
        else: length += to_html_abbrev(decl.data_type, span, nolinks)
    else:
        span.text = "#define"
        length += 7
    span.tail = " "
    if length > 20: etree.SubElement(dest, "br")
    span = etree.SubElement(dest, "span")
    span.set("class", "name")
    span.text = decl.name
    if decl.parameters != None: 
        span = etree.SubElement(dest, "span")
        span.set("class", "arglist")
        if not abbrev: to_html(decl.parameters, span, nolinks)
        else: to_html_abbrev(decl.parameters, span, nolinks)
    if decl.initializer != None and not abbrev:
        span = etree.SubElement(dest, "span")
        span.set("class", "init")
        span.text = " "
        to_html(decl.initializer, span, nolinks)
    

def typedef_decl(decl, dest):
    any_decl(decl, dest)    
    span = etree.SubElement(dest, "span")
    span.set("class", "specs")
    span.text = "using "
    span = etree.SubElement(dest, "span")
    span.set("class", "name")
    span.text = decl.name
    span = etree.Element("span")
    span.set("class", "type")
    length = to_html(decl.data_type, span)
    if length + len(decl.name) > 30:
        etree.SubElement(dest, "br")
    etree.SubElement(dest, "span").text = " = "
    dest.append(span)
    
    
def define_decl(decl, dest):
    func_var_decl(decl,dest)
    

def base_names(derived):
    names = set([derived.name])
    for base in derived.inherits_from:
        doxygen_id = base.get("refid")
        if doxygen_id in declarations: 
            names = names.union(base_names(declarations[doxygen_id]))
    return names
    
    
def struct_decl(decl, dest):
    any_decl(decl, dest)    
    span = etree.SubElement(dest, "span")
    span.set("class", "specs")
    span.text = localize(decl.kind) + " "
    span = etree.SubElement(dest, "span")
    span.set("class", "name")
    span.text = decl.name    

    comma = False
    for base in decl.inherits_from:
        etree.SubElement(dest, "br")
        span = etree.SubElement(dest, "span")
        span.text = "\xa0\xa0\xa0\xa0" + (", " if comma else ": ")
        if not comma: comma = True
        span.text += base.get("prot") + " "
        if base.get("virt") == "virtual": span.text += "virtual "
        if base.get("refid") in declarations:
            etree.SubElement(dest, "a", href = declarations[base.get("refid")].target_url).text = base.text
        else: etree.SubElement(dest, "span").text = base.text
        
                    
# Wraps a navigation and page content XHTML into a html file, writing it
#   page_title: What should appear in the <title> tag
#   navigation_html: A XHTML node for the navigation sidebar (left hand side)
#   content_html: A XHTML node for the page content (right hand side)
#   file_name: The file to write to.
def write_html(page_title, navigation_html, content_html, file_name): 
    html = etree.Element("html", nsmap = { None: "http://www.w3.org/1999/xhtml"} )
    # <html>
    
    head = etree.SubElement(html, "head")
    #   <head>
    etree.SubElement(head, "page_title").text = page_title
    meta = etree.SubElement(head, "meta")
    meta.set("http-equiv", "Content-Type")
    meta.set("content", "text/html, charset=utf-8")
    etree.SubElement(head, "link", rel="stylesheet", href="style.css")
    etree.SubElement(head, "link", rel="stylesheet", media="print", href="print.css")
    # </head>

    body = etree.SubElement(html, "body");
    # <body>
    outer_tr = etree.SubElement(etree.SubElement(body, "table"), "tr", id="outer")
    # <table><tr>
    etree.SubElement(outer_tr, "td", id="navigation_html-td").append(navigation_html)
    etree.SubElement(outer_tr, "td", id="content-td").append(content_html)
    # </table></tr>
    # </body>
    # </html>
    
    output_file = open(file_name, "wb")
    output_file.write(etree.tostring(html, pretty_print=True, encoding='UTF-8', 
                           method = "html", doctype='<!DOCTYPE html>'))
    output_file.close()
    
    
    
global_nav = []
global_nav_dict = dict()
for glob in root.all_members:
    if glob in declarations: 
        mb = declarations[glob]
        if not mb.kind in global_nav_dict: global_nav_dict[mb.kind] = []
        global_nav_dict[mb.kind].append(mb)

def add_nav_section(name, kinds):
    ul = None
    for kind in kinds:
        if kind in global_nav_dict:
            if ul == None:
                h3 = etree.Element("h3")
                h3.text = localize(name).title()
                global_nav.append(h3)
                ul = etree.Element("ul")
                global_nav.append(ul)
            for e in sorted(global_nav_dict[kind], key=lambda x: x.name):
                etree.SubElement(etree.SubElement(ul, "li"), "a", href = e.target_url).text = \
                    e.page_title if e.page_title != None else e.name
    
add_nav_section("groups", [ "group" ])
add_nav_section("special pages", [ "page" ])
add_nav_section("headers", [ "dir", "file" ])

   
def tree(decls, nav=None, parent="", parent_links=etree.Element("span")):  
    decls.sort(key=lambda e: hash(e.definition))
    decls.sort(key=lambda e: e.name)
      
    # For specialized class templates, do not inline specializations; 
    # rather add child_links to the specialization pages
    if len(decls) > 1 and (decls[0].kind == "class" or decls[0].kind == "struct"):
        specializations = copy.copy(decls)
        min_decl = None
        for decl in specializations:
            if min_decl == None or len(decl.name) < len(min_decl.name):
                min_decl = decl
        specializations.remove(min_decl)
        decls = [ min_decl ]
    else: specializations = []
    full_name = decls[0].full_name
    page_title = decls[0].page_title.title() if decls[0].page_title != None else decls[0].name
            
    caption = etree.Element("h2")    
    links = copy.deepcopy(parent_links)
    if len(links) > 0 and decls[0].kind != "file" and decls[0].kind != "dir":        
        links[len(links)-1].tail = "::"
    child_links = copy.deepcopy(links)
    if full_name != "":
        etree.SubElement(child_links, "a", href=decls[0].target_url).text = decls[0].name
    etree.SubElement(links, "span").text = page_title
    links.set("class", "page-caption")
    links.tail = " "
    caption.append(links)
    
    if decls[0].kind != "root" and decls[0].kind != "page":
        caption_type = etree.SubElement(caption, "span")
        caption_type.set("class", "page-type")
        caption_type.text = "(" + localize(decls[0].kind) + ")"
        
    if decls[0].kind == "root":
        nav = etree.Element("div", id="nav")
        etree.SubElement(nav, "div", id="nav-overlay")
        nav_head = etree.Element("h2")
        nav_head_up = etree.SubElement(nav_head, "span")
        nav_head_up.set("class", "nav-up")
        nav_head_up.text = "Navigation"
        for e in global_nav: nav.append(copy.deepcopy(e))
       
    child_nav = etree.Element("div", id="nav")
    etree.SubElement(child_nav, "div", id="nav-overlay")
    child_nav_head = etree.SubElement(child_nav, "h2")
    child_nav_up = etree.SubElement(child_nav_head, "a")
    child_nav_up.text = page_title
    child_nav_up.set("class", "nav-up")
    child_nav_up.set("href", decls[0].target_url)
    
    def add_nav_item(ul, name, href):
        etree.SubElement(etree.SubElement(ul, "li"), "a", href=href).text = name
        
    page = etree.Element("div", id="content")
    page.append(caption)
    overview = etree.SubElement(page, "div", id="overview")
        
        
    # Includes for any of the definitions in "decl"
    include_dict = dict()
    for decl in decls:
        if decl.kind != "file":
            for inc in decl.include_files:
                include_dict[inc.get("refid")] = inc
            
    if len(include_dict) > 0:
        include_div = etree.SubElement(overview, "p")
        include_div.set("class", "include")
                            
        first = True
        for inc in sorted(include_dict.values(), key = lambda x: x.text):     
            if not first: etree.SubElement(include_div, "br")
            else: first = False
            include_span = etree.SubElement(include_div, "span")    
            include_span.text = '#include <'
            a = etree.SubElement(include_span, "a")
            if inc.get("refid") in declarations:
                include_file = declarations[inc.get("refid")]
                a.set("href", include_file.target_url)
                a.text = include_file.full_name
            else:
                a.text = inc.text
            a.tail = ">"
        
    inline = etree.Element("div", id="inline")
    inline_ul = etree.Element("ul")
    inline_ul.set("class", "inline-list")
    if len(decls) > 1: 
        overview_ol = etree.SubElement(overview, "ol")
        overview_ol.set("class", "overview-list")
        inline_ol = etree.SubElement(inline, "ol")
        inline_ol.set("class", "details-list")
        
    n = 1
    for decl in decls:
        details_div = etree.Element("div")
        if len(decls) > 1:
            def_div = etree.SubElement(inline_ol, "li")
        else: 
            def_div = etree.SubElement(overview, "div")
    
        if len(decls) > 1 and (decl.kind == "function" or decl.kind == "variable"):
            li = etree.SubElement(overview_ol, "li")
            li.set("class", "def")
            a = etree.SubElement(li, "a", href="#details%d" % n)
            if decl.kind == "function" or decl.kind == "variable":
                func_var_decl(decl, a, nolinks=True, abbrev=True)
                li.append(a)
            
        if decl.kind == "function" or decl.kind == "variable":
            p = etree.SubElement(def_div, "p")
            etree.SubElement(p, "a", name="details%d" % n)
            func_var_decl(decl, p)
        elif decl.kind == "class" or decl.kind == "struct":
            p = etree.SubElement(def_div, "p")
            struct_decl(decl, p)
                   
        def_div.set("class", "def")
        if decl.brief_description != None:
            div = etree.SubElement(def_div, "div")
            div.set("class", "brief")
            to_html(decl.brief_description, div)
            
        if decl.kind == "enum":
            div = etree.SubElement(def_div, "div")
            etree.SubElement(div, "h4").text = "Enumeration values:"
            par = etree.SubElement(div, "div")
            par.set("class", "par")
            table = etree.SubElement(par, "table")
            table.set("class", "paramlist")
            for val in decl.enum_values:
                tr = etree.SubElement(table, "tr")
                td = etree.SubElement(tr, "td")
                td.set("class", "paramname")
                xp = val.xpath("name")
                if len(xp) > 0: td.text = xp[0].text
                td = etree.SubElement(tr, "td")
                xp = val.xpath("briefdescription")
                if len(xp) > 0: to_html(xp[0], td)
            
        if decl.detailed_description != None:
            div = etree.SubElement(def_div, "div")
            div.set("class", "details")
            to_html(decl.detailed_description, div)
            
        base_classes = base_names(decl)  
        
        children = []
            
        members = dict()
        for doxygen_id in decl.all_members:
            if doxygen_id not in declarations: continue
            e = declarations[doxygen_id]
            
            if e.visibility == "private" or e.visibility == "protected": key = e.visibility
            else: key = "public"
            if e.is_static and (e.kind == "function" or e.kind == "variable"): 
                key += " static"
            if e.kind == "struct" or e.kind == "class" or e.kind == "typedef" or e.kind == "enum":
                key += " types"
            else:
                key += " " + e.kind + "s"
            if key not in members:
                members[key] = dict()                                
            cat = members[key]       
            
            if e.name in base_classes: group_name = "(constructor)"
            elif e.name[0] == '~': group_name = "(destructor)"
            elif "<" in e.name: group_name = e.name[0 : e.name.find("<")].strip()
            else: group_name = e.name
            
            if group_name not in cat:
                cat[group_name] = []
            cat[group_name].append(e)
           
        enabled_vis = [ "public" ]
        if config["show_protected"]: enabled_vis.append("protected")
        if config["show_private"]: enabled_vis.append("private")
           
        for vis in enabled_vis:
            for stat in [ "", " static" ]:
                member_kinds = [ "namespaces", "types", "functions", "variables", "defines" ]
                if decl.kind == "dir": member_kinds += [ "dirs", "files" ] 
                for dcat in member_kinds:
                    key = vis + stat + " " + dcat
                    if key not in members: continue
                    div = etree.Element("div")
                    if (dcat == "types" or dcat == "variables" or dcat == "functions") \
                            and (decls[0].kind == "struct" or decls[0].kind == "class"):
                        cat_title = localize(vis) + " "
                        if stat != "": cat_title += localize("static") + " "
                    else:
                        cat_title = ""
                    h3 = etree.SubElement(div, "h3")
                    h3.text = (cat_title + localize(dcat)).title()
                    
                    nav_div = copy.deepcopy(div)
                    nav_ul = etree.SubElement(nav_div, "ul")
                    table = etree.Element("table")
                    table.set("class", "decllist")
                    for group_name, e in sorted(members[key].items()):
                        # Doxygen lists all inherited constructors and destructors as members.
                        if group_name == "(destructor)":
                            dtors = []
                            for f in e:
                                if f.name == "~" + decl.name: dtors.append(f)
                            if len(dtors) > 0: 
                                children.append((dtors, full_name, child_links))
                                href = dtors[0].target_url
                            else: continue
                        elif not e[0].inline_doc:
                            children.append((e, full_name, child_links))
                            href = min(e, key=lambda x: x.name).target_url
                        else: 
                            for f in sorted(e, key=lambda x: x.name):
                                anchor = f.target_url_anchor
                                href = f.target_url
                                li = etree.SubElement(inline_ul, "li")
                                li.set("class", "details def")
                                decl_div = etree.SubElement(li, "div")
                                etree.SubElement(decl_div, "a", name=anchor)
                                if f.kind == "typedef":
                                    typedef_decl(f, etree.SubElement(decl_div, "p"))
                                elif f.kind == "define":
                                    define_decl(f, etree.SubElement(decl_div, "p"))
                                else:
                                    func_var_decl(f, etree.SubElement(decl_div, "p"))                                
                                if f.brief_description != None:
                                    brief = etree.SubElement(li, "div")
                                    brief.set("class", "brief")
                                    to_html(f.brief_description, brief)
                                if f.detailed_description != None:
                                    details = etree.SubElement(li, "div")
                                    details.set("class", "details")
                                    to_html(f.detailed_description, details)
                        tr = etree.SubElement(table, "tr")
                        if e[0].kind not in [ "group", "file", "page", "dir" ]:
                            td = etree.SubElement(tr, "td", )
                            td.set("class", "decltype")
                            if e[0].kind == "variable": 
                                to_html_abbrev(e[0].data_type, td)
                            elif e[0].kind == "function": 
                                if group_name == "(constructor)": td.text = "constructor"
                                elif group_name == "(destructor)": td.text = "destructor"
                                else: td.text = "function"
                            elif e[0].kind == "define":
                                td.text = "#define"
                            else: td.text = e[0].kind
                        td = etree.SubElement(tr, "td")              
                        td.set("class", "declname")        
                        a = etree.SubElement(td, "a", href = href)
                        a.set("class", "name")
                        if e[0].page_title != None: a.text = e[0].page_title
                        elif group_name == "(constructor)": a.text = decl.name
                        elif group_name == "(destructor)": a.text = "~" + decl.name
                        else: a.text = group_name
                        span = etree.SubElement(td, "span")           
                        span.set("class", "init")
                        if e[0].kind == "typedef": 
                            to_html_abbrev(e[0].data_type, span)
                            span.text = " = " + (span.text if span.text else "")
                        add_nav_item(nav_ul, a.text, href)
                        
                    div.append(table)
                    overview.append(div)
                    child_nav.append(nav_div)
                    if  len(details_div) > 0:
                        inline.append(details_div)
                        
        for key in [ "public groups", "public pages", "public files", "public dirs" ]:     
            if key in members:
                for group in members[key].values(): 
                    for coll in group:
                        children.append(([coll], full_name, child_links))
                    
        n += 1
            
    if len(inline_ul) > 0: 
        inline.append(inline_ul)
        
    if len(decls) > 1 or len(inline) > 0:
        etree.SubElement(page, "h3").text = "Details"
    
    if len(specializations) > 0:
        div = etree.SubElement(inline, "div")
        h3 = etree.SubElement(div, "h3")
        h3.text = "Template Specializations"
        nav_div = copy.deepcopy(div)
        nav_ul = etree.SubElement(nav_div, "ul")
        table = etree.SubElement(div, "table")
        table.set("class", "decllist")
        for s in specializations:
            href = s.target_url
            children.append(([s], parent, parent_links))
            tr = etree.SubElement(table, "tr")
            td = etree.SubElement(tr, "td")
            td.set("class", "decltype")
            td.text = s.kind
            td = etree.SubElement(tr, "td")
            td.set("class", "declname")
            add_nav_item(nav_ul, s.name, s.target_url)
            a = etree.SubElement(td, "a", href=s.target_url)
            a.set("class", "name")
            a.text = s.name
            
    for e in global_nav: child_nav.append(copy.deepcopy(e))
    
    if len(decls) > 1 or len(inline) > 0:
        page.append(inline)
    write_html(page_title, nav, page, output_dir + "/" + decls[0].target_url)
    
    for all_decls, parent, parent_links in children:
        child_decls = []
        for d in all_decls: 
            for e in decls: 
                if d.parent == e or d in specializations:
                    child_decls.append(d)
        if len(child_decls) > 0:
            tree(child_decls, copy.deepcopy(child_nav), parent, child_links)
    
tree([root])

