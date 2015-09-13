
# original author unknown

import re
 
term_regex = re.compile( r'''(?mx)
    \s*(?:
        (?P<brackl>\()|
        (?P<brackr>\))|
        (?P<num>[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)|
        (?P<quo>"(?:[^\\]|(?:\\.))*")|
        (?P<s>[^(^)\s]+)
       )''')
 
 
def loads(sexp):
    stack = []
    out = []
    for termtypes in term_regex.finditer(sexp):
        term, value = [(t,v) for t,v in termtypes.groupdict().items() if v][0]
        if term == 'brackl':
            stack.append(out)
            out = []
        elif term == 'brackr':
            if not stack:
              raise SyntaxError( "Bad nesting in s-expression: %s" % sexp )
            tmpout, out = out, stack.pop(-1)
            out.append(tmpout)
        elif term == 'num':
            v = float(value)
            if v.is_integer(): 
              v = int(v)
            out.append(v)
        elif term == 'quo':
            out.append(value[1:-1])
        elif term == 's':
            out.append(value)
        else:
            raise NotImplementedError("Error in s-expression: %r" % (term, value))
    if stack:
      raise SyntaxError( "Bad nesting in s-expression: %s" % sexp )
    return out[0]


def dumps(exp):
    out = ''
    if type(exp) == type([]):
        out += '(' + ' '.join(dumps(x) for x in exp) + ')'
    elif type(exp) == type('') and re.search(r'[\s()]', exp):
        out += '"%s"' % repr(exp)[1:-1].replace('"', '\"')
    else:
        out += '%s' % exp
    return out
 
 