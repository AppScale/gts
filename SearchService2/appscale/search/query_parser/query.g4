grammar query ;

/*
To build this grammar you need to have antlr4.
4.7.2 was used initially - it generates much more performant  parser
comparing to 4.5.3 (which was only available version in ubuntu xenial repo).
Visit https://www.antlr.org/ to see how to run antlr4 from latest jar file.

Then execute following from terminal:
```
cd "${APPSCALE_HOME}/SearchService2/appscale/search/query_parser"
antlr4 -Dlanguage=Python3 -o ./ -lib ./ -package appscale.search.query_parser ./query.g4
```
*/

// Lexer rules:
OR         : 'OR' ;
AND        : 'AND' ;
NOT        : 'NOT';
STEM       : '~' ;
EQUALS     : '=' | ':' ;
LESS       : '<' ;
LESS_EQ    : '<=' ;
GREATER    : '>' ;
GREATER_EQ : '>=' ;

WORD          : ~[ \t\r\n\\"~=<>:(),]+ ;

QUOTED        : ["] ('\\"' | ~["])* ["] ;
LEFTBRACKET   : [(] ;
RIGHTBRACKET  : [)] ;
WS            : [ \t\r\n]+ -> skip ;


// Grammar rules:
query            : exprsSeq EOF ;

exprsGroup       : LEFTBRACKET exprsSeq RIGHTBRACKET ;
exprsSeq         : (exprsGroup | expr) ((AND | OR)? (exprsGroup | expr))* ;

expr             : unaryExpr
                 | WORD (EQUALS | LESS | LESS_EQ | GREATER | GREATER_EQ) (unaryExpr | unaryExprsGroup) ;

unaryExprsGroup  : LEFTBRACKET unaryExprsSeq RIGHTBRACKET ;
unaryExprsSeq    : (unaryExprsGroup | unaryExpr) ((AND | OR)? (unaryExprsGroup | unaryExpr))*  ;

unaryExpr        : (NOT | STEM)? (WORD | QUOTED) ;
