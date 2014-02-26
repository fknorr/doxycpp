#!/usr/bin/env python

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


if len(sys.argv) != 2:
    print("Syntax: %s <output directory>" % sys.argv[0])
    sys.exit(1)
else:
    html_dir = sys.argv[1]


# A Declaration, extracted from XML
class decl:
    def __init__(self, _id):
        self.parent = None
        self.id = _id
        self.vis = "public"
        self.static = False
        self.kind = "none"
        self.name = ""
        self.full_name = ""
        self.brief = None
        self.members = set()
        self.all_members = set()
        self.url = ""
        self.anchor = ""
        self.definition = None
        self.includes = []
        self.inline = False
        self.virtual = False
        self.tplist = None
        self.palist = None
        self.init = None
        self.type = None
        self.enumvals = []
        self.bases = []
        self.inline_doc = False
        self.details = None
        self.is_collection = False
        self.title = None
        self.args = None
        self.explicit = False

# Maps weird Doxygen (like "classfn_1_1definition__array_4") IDs to "decl" instances
di = dict()

# Reads a <compounddef> or <memberdef> tag, updating "di"
def read_memberdef(root, ref, kind):
    ident = root.get("id")
    if ref != None: 
        ref.all_members.add(ident)
        ref.members.add(ident)
    if not ident in di:
        di[ident] = decl(ident)    
        mb = di[ident]        
        mb.kind = kind 
        mb.inline_doc = (kind == "typedef" or kind == "variable" or kind == "define")
        mb.is_collection = (kind == "group" or kind == "page" or kind == "file")
        mb.vis = root.get("prot")
        mb.static = root.get("static") == "yes"
        mb.virtual = root.get("virtual") == "yes"
        mb.inline = root.get("inline") == "yes"
        mb.explicit = root.get("explicit") == "yes"

        for e in root.iterchildren(tag=etree.Element):
            if e.tag == "type": mb.type = e
            elif e.tag == "title": mb.title = e.text
            elif e.tag == "definition": mb.definition = e
            elif e.tag == "argsstring": mb.args = e
            elif e.tag == "name" or e.tag == "compoundname": mb.name = e.text
            elif e.tag == "inbodydescription": mb.ibdescr = e
            elif e.tag == "briefdescription": mb.brief = e
            elif e.tag == "initializer": mb.init = e
            elif e.tag == "includes": mb.includes.append(e)
            elif e.tag == "detaileddescription": mb.details = e
            elif e.tag == "templateparamlist": mb.tplist = e
            elif e.tag == "enumvalue": mb.enumvals.append(e)
            elif e.tag == "basecompoundref": mb.bases.append(e)
            elif e.tag == "param":
                for f in e.iterchildren(tag=etree.Element):
                    if kind == "define" and f.tag == "defname":
                        if mb.args != None: mb.args.text += ", "
                        else: 
                            mb.args = etree.Element("argsstring")
                            mb.args.text = "("
                        mb.args.text += f.text
        if kind == "define" and mb.args != None:
            mb.args.text += ")"    
        return mb
    else: return di[ident]

# Read XML files
for xml in os.listdir():
    xtree = etree.parse(xml)
    # <compounddef>s contain <memberdef>s and <innerclass>es, which hold the main information
    tables = xtree.xpath("/doxygen/compounddef")
    for t in tables: 
        ref = read_memberdef(t, None, t.get("kind"))
        for e in t.iterchildren(tag=etree.Element):
            if e.tag == "innerclass" or e.tag == "innerfile" or e.tag == "innerdir":
                ref.members.add(e.get("refid"))
                ref.all_members.add(e.get("refid"))
            elif e.tag == "sectiondef": 
                for f in e.iterchildren(tag="memberdef"):
                    read_memberdef(f, ref, f.get("kind"))
            elif e.tag == "listofallmembers" and not ref.is_collection:
                for f in e.iterchildren(tag="member"):
                    ref.all_members.add(f.get("refid"))
        
# Unresolved identifiers
unres = []

# Takes an arbitrary string, removes all non-alnum and non-_ characters, concatenating it 
# with -, and adding a hash to avoid collisions
def urlify(string):
    r = ""
    lastdot = True
    for c in string:
        if (((c >= '0' and c <= '9') or (c >= 'a' and c <= 'z') or (c >= 'A' and c <= 'Z') or c == '_')): 
            r += c.lower()
            lastdot = False
        elif not lastdot:
            r += '-'
            if c == '~': r += "not-"
            lastdot = True
    if not lastdot: r += '-'
    r += hashlib.md5(bytearray(string, 'utf-8')).hexdigest()[0:4]
    return r


def hierarchy(root):
    if not root.is_collection: 
        for id in root.members:
            if id in di and di[id].parent == None:
                di[id].parent = root
                hierarchy(di[id])   
                if di[id].includes == []: di[id].includes = root.includes

root = decl("root")
root.kind = "root"
root.name = ""

namespaces = {}

# Partially recursive
for key, val in di.items():
    # Add parents where a hierarchy exists in the XML
    hierarchy(val)
    # Namespaces don't contain each other, remember their full names to resolve them later
    if val.kind == "namespace":
        namespaces[val.name] = key

for key, val in di.items(): 
    if val.parent == None:
        new_parent = root;
        # Resolve nested namespaces by their scoped name
        if val.kind == "namespace" and "::" in val.name:
            container = namespaces[val.name[0:val.name.rfind("::")]]
            if container and container in di: new_parent = di[container]
        val.parent = new_parent
        new_parent.all_members.add(key)


# Brings all names of declarations to a common format, recursively
def init_names(decl):
    if len(decl.name) > 0 and decl.name[0] == '@':
        decl.name = "(anonymous)"
    if "::" in decl.name:
        start = 0; level = 0; i=0
        for c in decl.name:
            if c == '<': level += 1
            elif c == '>': level -= 1
            elif c == ':' and level == 0: start = i+1
            i += 1
        decl.name = decl.name[start:]
    
    if decl.kind == "dir": decl.name += "/"
        
    if decl.parent != None and decl.kind != "file" and decl.parent.full_name != "": 
        decl.full_name = decl.parent.full_name + "::" + decl.name
    elif decl.parent != None: 
        decl.full_name = decl.parent.full_name + decl.name
    
    def page_url(kind, fn):
        return kind + "-" + urlify(fn) if fn != "" else "index"
    
    if not decl.inline_doc:
        decl.url = page_url(decl.kind, decl.full_name) + ".html"
    elif decl.parent.url != None: 
        decl.anchor = page_url(decl.kind, decl.full_name)
        decl.url = decl.parent.url + "#" + decl.anchor
        
    if not decl.is_collection:
        for id in decl.all_members:
            if id in di: init_names(di[id])

init_names(root)
root.title = localize("index")
root.url = "index.html"

        
# Replaces template parameters in a string with '<...>'
def abbrev(text, depth, skipped=False):
    if text == None: return None, depth
    out = ""
    for c in text:
        if c == '<':
            depth += 1
            if depth == 1: out += c
        elif c == '>' and depth > 0: 
            depth -= 1
            if depth == 0:
                if skipped: out += " ... "
                out += c
        elif depth > 0: skipped = True
        else: out += c
    return out, depth
    
def to_html_abbrev(tree, dest, nolinks=False):
    depth = 0
    dest.text, depth = abbrev(tree.text, depth)
    length = len(dest.text) if dest.text != None else 0
    for e in tree.iterchildren(tag="ref"):
        a = etree.SubElement(dest, "a" if not nolinks else "span")
        if e.get("refid") in di and not nolinks: 
            a.set("href", di[e.get("refid")].url)
        a.text, depth = abbrev(e.text, depth)
        a.tail, depth = abbrev(e.tail, depth)
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
                if e.get("refid") and e.get("refid") in di and di[e.get("refid")].url != None:
                    a.set("href", di[e.get("refid")].url)
            else:
                a = etree.SubElement(dest, "span")
            a.tail = e.tail; addlen(e.tail)
            a.text = e.text; addlen(e.tail)
        elif e.tag == "para":
            length[0] += to_html(e, dest)
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
    if decl.tplist != None:
        span = etree.SubElement(dest, "span")
        span.set("class", "template")
        span.text = "template <"
        comma = False
        for param in decl.tplist.iterchildren(tag=etree.Element):
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
    if decl.explicit: span.text += "explicit "
    if decl.static: span.text += "static "
    if decl.virtual: span.text += "virtual "
    length = len(span.text)
    span = etree.SubElement(dest, "span")
    span.set("class", "type")
    if decl.kind != "define":
        if not abbrev: length += to_html(decl.type, span, nolinks)
        else: length += to_html_abbrev(decl.type, span, nolinks)
    else:
        span.text = "#define"
        length += 7
    span.tail = " "
    if length > 20: etree.SubElement(dest, "br")
    span = etree.SubElement(dest, "span")
    span.set("class", "name")
    span.text = decl.name
    if decl.args != None: 
        span = etree.SubElement(dest, "span")
        span.set("class", "arglist")
        if not abbrev: to_html(decl.args, span, nolinks)
        else: to_html_abbrev(decl.args, span, nolinks)
    if decl.init != None and not abbrev:
        span = etree.SubElement(dest, "span")
        span.set("class", "init")
        span.text = " "
        to_html(decl.init, span, nolinks)
    

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
    length = to_html(decl.type, span)
    if length + len(decl.name) > 30:
        etree.SubElement(dest, "br")
    etree.SubElement(dest, "span").text = " = "
    dest.append(span)
    
    
def define_decl(decl, dest):
    func_var_decl(decl,dest)
    

def base_names(derived):
    names = set([derived.name])
    for base in derived.bases:
        id = base.get("refid")
        if id in di: 
            names = names.union(base_names(di[id]))
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
    for base in decl.bases:
        etree.SubElement(dest, "br")
        span = etree.SubElement(dest, "span")
        span.text = "\xa0\xa0\xa0\xa0" + (", " if comma else ": ")
        if not comma: comma = True
        span.text += base.get("prot") + " "
        if base.get("virt") == "virtual": span.text += "virtual "
        if base.get("refid") in di:
            etree.SubElement(dest, "a", href = di[base.get("refid")].url).text = base.text
        else: etree.SubElement(dest, "span").text = base.text
        
                    
# Wraps a <body> tag in a html file, writes it
def write_html(title, nav, cont, url): 
    html = etree.Element("html", nsmap = { None: "http://www.w3.org/1999/xhtml"} )
    head = etree.SubElement(html, "head")
    etree.SubElement(head, "title").text = title
    meta = etree.SubElement(head, "meta")
    meta.set("http-equiv", "Content-Type")
    meta.set("content", "text/html, charset=utf-8")
    etree.SubElement(head, "link", rel="stylesheet", href="style.css")
    etree.SubElement(head, "link", rel="stylesheet", media="print", href="print.css")
    tr = etree.SubElement(etree.SubElement(etree.SubElement(html, "body"), "table"), "tr", id="outer")
    etree.SubElement(tr, "td", id="nav-td").append(nav)
    etree.SubElement(tr, "td", id="content-td").append(cont)
    f = open(url, "wb")
    f.write(etree.tostring(html, pretty_print=True, encoding='UTF-8', 
                           method = "html", doctype='<!DOCTYPE html>'))
    f.close()
    
    
    
global_nav = []
global_nav_dict = dict()
for glob in root.all_members:
    if glob in di: 
        mb = di[glob]
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
                etree.SubElement(etree.SubElement(ul, "li"), "a", href = e.url).text = \
                    e.title if e.title != None else e.name
    
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
    page_title = decls[0].title.title() if decls[0].title != None else decls[0].name
            
    caption = etree.Element("h2")    
    links = copy.deepcopy(parent_links)
    if len(links) > 0 and decls[0].kind != "file" and decls[0].kind != "dir":        
        links[len(links)-1].tail = "::"
    child_links = copy.deepcopy(links)
    if full_name != "":
        etree.SubElement(child_links, "a", href=decls[0].url).text = decls[0].name
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
    child_nav_up.set("href", decls[0].url)
    
    def add_nav_item(ul, name, href):
        etree.SubElement(etree.SubElement(ul, "li"), "a", href=href).text = name
        
    page = etree.Element("div", id="content")
    page.append(caption)
    overview = etree.SubElement(page, "div", id="overview")
        
        
    # Includes for any of the definitions in "decl"
    include_dict = dict()
    for decl in decls:
        if decl.kind != "file":
            for inc in decl.includes:
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
            if inc.get("refid") in di:
                include_file = di[inc.get("refid")]
                a.set("href", include_file.url)
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
        if decl.brief != None:
            div = etree.SubElement(def_div, "div")
            div.set("class", "brief")
            to_html(decl.brief, div)
            
        if decl.kind == "enum":
            div = etree.SubElement(def_div, "div")
            etree.SubElement(div, "h4").text = "Enumeration values:"
            par = etree.SubElement(div, "div")
            par.set("class", "par")
            table = etree.SubElement(par, "table")
            table.set("class", "paramlist")
            for val in decl.enumvals:
                tr = etree.SubElement(table, "tr")
                td = etree.SubElement(tr, "td")
                td.set("class", "paramname")
                xp = val.xpath("name")
                if len(xp) > 0: td.text = xp[0].text
                td = etree.SubElement(tr, "td")
                xp = val.xpath("briefdescription")
                if len(xp) > 0: to_html(xp[0], td)
            
        if decl.details != None:
            div = etree.SubElement(def_div, "div")
            div.set("class", "details")
            to_html(decl.details, div)
            
        base_classes = base_names(decl)  
        
        children = []
            
        members = dict()
        for id in decl.all_members:
            if id not in di: continue
            e = di[id]
            
            if e.vis == "private" or e.vis == "protected": key = e.vis
            else: key = "public"
            if e.static and (e.kind == "function" or e.kind == "variable"): 
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
                                href = dtors[0].url
                            else: continue
                        elif not e[0].inline_doc:
                            children.append((e, full_name, child_links))
                            href = min(e, key=lambda x: x.name).url
                        else: 
                            for f in sorted(e, key=lambda x: x.name):
                                anchor = f.anchor
                                href = f.url
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
                                if f.brief != None:
                                    brief = etree.SubElement(li, "div")
                                    brief.set("class", "brief")
                                    to_html(f.brief, brief)
                                if f.details != None:
                                    details = etree.SubElement(li, "div")
                                    details.set("class", "details")
                                    to_html(f.details, details)
                        tr = etree.SubElement(table, "tr")
                        if e[0].kind not in [ "group", "file", "page", "dir" ]:
                            td = etree.SubElement(tr, "td", )
                            td.set("class", "decltype")
                            if e[0].kind == "variable": 
                                to_html_abbrev(e[0].type, td)
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
                        if e[0].title != None: a.text = e[0].title
                        elif group_name == "(constructor)": a.text = decl.name
                        elif group_name == "(destructor)": a.text = "~" + decl.name
                        else: a.text = group_name
                        span = etree.SubElement(td, "span")           
                        span.set("class", "init")
                        if e[0].kind == "typedef": 
                            to_html_abbrev(e[0].type, span)
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
            href = s.url
            children.append(([s], parent, parent_links))
            tr = etree.SubElement(table, "tr")
            td = etree.SubElement(tr, "td")
            td.set("class", "decltype")
            td.text = s.kind
            td = etree.SubElement(tr, "td")
            td.set("class", "declname")
            add_nav_item(nav_ul, s.name, s.url)
            a = etree.SubElement(td, "a", href=s.url)
            a.set("class", "name")
            a.text = s.name
            
    for e in global_nav: child_nav.append(copy.deepcopy(e))
    
    if len(decls) > 1 or len(inline) > 0:
        page.append(inline)
    write_html(page_title, nav, page, html_dir + "/" + decls[0].url)
    
    for all_decls, parent, parent_links in children:
        child_decls = []
        for d in all_decls: 
            for e in decls: 
                if d.parent == e or d in specializations:
                    child_decls.append(d)
        if len(child_decls) > 0:
            tree(child_decls, copy.deepcopy(child_nav), parent, child_links)
    
tree([root])

