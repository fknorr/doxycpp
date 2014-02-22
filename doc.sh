#!/bin/sh

PROJECT_ROOT=`dirname $(readlink -f $0)`
DOXYFILE="$PROJECT_ROOT/Doxyfile"
INCLUDE_DIR="$PROJECT_ROOT/include"
DOC_DIR="$PROJECT_ROOT/doc"

DOXYCPP=`dirname $(readlink -f $0)`/doxycpp.py
DOXYGEN=doxygen
PYTHON3=python3
GREP=grep
MKDIR=mkdir

#------------------------

cd "$INCLUDE_DIR"
rm -rf "$DOC_DIR/xml" "$DOC_DIR/html"

if [ "$1" == "-v" ]; then 
    FILTER="error:\|warning:"
else 
    FILTER="error:"
fi


"$DOXYGEN" "$DOXYFILE" 2>&1 | "$GREP" "$FILTER"

if [ $? -ne 0 ] && [ -d "$DOC_DIR/xml" ]; then
    cd "$DOC_DIR/xml"
    if [ ! -e "$DOC_DIR/html" ]; then 
        "$MKDIR" "$DOC_DIR/html"
    fi
    
    "$PYTHON3" "$DOXYCPP" "$DOC_DIR/html"
    if [ $? -ne 0 ]; then 
        echo "*** DoxyC++ failed!" >&2
        exit $?
    fi
    
    if [ -e "$DOC_DIR/src" ] && [ "`echo "$DOC_DIR/src"/*`" != "$DOC_DIR/src/*" ]; then
        cp -rf "$DOC_DIR/src"/* "$DOC_DIR/html"
    fi
else
    echo "*** Doxygen failed!" >&2
    exit $?
fi

