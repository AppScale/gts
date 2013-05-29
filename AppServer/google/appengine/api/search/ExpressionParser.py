#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import sys
from google.appengine._internal.antlr3 import *
from google.appengine._internal.antlr3.compat import set, frozenset

from google.appengine._internal.antlr3.tree import *






HIDDEN = BaseRecognizer.HIDDEN


DOLLAR=49
EXPONENT=44
LT=11
LSQUARE=23
ASCII_LETTER=47
LOG=35
SNIPPET=39
OCTAL_ESC=52
MAX=36
FLOAT=27
COUNT=31
NAME_START=45
NOT=10
AND=7
EOF=-1
LPAREN=21
INDEX=5
RPAREN=22
DISTANCE=32
QUOTE=42
NAME=26
ESC_SEQ=43
POW=38
T__53=53
COMMA=29
PLUS=17
DIGIT=41
EQ=15
NE=16
GE=14
XOR=9
SWITCH=40
UNICODE_ESC=51
HEX_DIGIT=50
UNDERSCORE=48
INT=24
MIN=37
MINUS=18
RSQUARE=25
GEOPOINT=33
PHRASE=28
ABS=30
WS=46
OR=8
NEG=4
GT=13
LEN=34
DIV=20
TIMES=19
COND=6
LE=12


tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "NEG", "INDEX", "COND", "AND", "OR", "XOR", "NOT", "LT", "LE", "GT",
    "GE", "EQ", "NE", "PLUS", "MINUS", "TIMES", "DIV", "LPAREN", "RPAREN",
    "LSQUARE", "INT", "RSQUARE", "NAME", "FLOAT", "PHRASE", "COMMA", "ABS",
    "COUNT", "DISTANCE", "GEOPOINT", "LEN", "LOG", "MAX", "MIN", "POW",
    "SNIPPET", "SWITCH", "DIGIT", "QUOTE", "ESC_SEQ", "EXPONENT", "NAME_START",
    "WS", "ASCII_LETTER", "UNDERSCORE", "DOLLAR", "HEX_DIGIT", "UNICODE_ESC",
    "OCTAL_ESC", "'.'"
]




class ExpressionParser(Parser):
    grammarFileName = ""
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"
    tokenNames = tokenNames

    def __init__(self, input, state=None):
        if state is None:
            state = RecognizerSharedState()

        Parser.__init__(self, input, state)


        self.dfa10 = self.DFA10(
            self, 10,
            eot = self.DFA10_eot,
            eof = self.DFA10_eof,
            min = self.DFA10_min,
            max = self.DFA10_max,
            accept = self.DFA10_accept,
            special = self.DFA10_special,
            transition = self.DFA10_transition
            )







        self._adaptor = CommonTreeAdaptor()



    def getTreeAdaptor(self):
        return self._adaptor

    def setTreeAdaptor(self, adaptor):
        self._adaptor = adaptor

    adaptor = property(getTreeAdaptor, setTreeAdaptor)



    def mismatch(input, ttype, follow):
      raise MismatchedTokenException(ttype, input)

    def recoverFromMismatchedSet(input, e, follow):
      raise e



    class expression_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def expression(self, ):

        retval = self.expression_return()
        retval.start = self.input.LT(1)

        root_0 = None

        EOF2 = None
        conjunction1 = None


        EOF2_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_conjunction_in_expression92)
                conjunction1 = self.conjunction()

                self._state.following.pop()
                self._adaptor.addChild(root_0, conjunction1.tree)
                EOF2=self.match(self.input, EOF, self.FOLLOW_EOF_in_expression94)

                EOF2_tree = self._adaptor.createWithPayload(EOF2)
                self._adaptor.addChild(root_0, EOF2_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class condExpr_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def condExpr(self, ):

        retval = self.condExpr_return()
        retval.start = self.input.LT(1)

        root_0 = None

        COND4 = None
        conjunction3 = None

        addExpr5 = None


        COND4_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_conjunction_in_condExpr107)
                conjunction3 = self.conjunction()

                self._state.following.pop()
                self._adaptor.addChild(root_0, conjunction3.tree)

                alt1 = 2
                LA1_0 = self.input.LA(1)

                if (LA1_0 == COND) :
                    alt1 = 1
                if alt1 == 1:

                    pass
                    COND4=self.match(self.input, COND, self.FOLLOW_COND_in_condExpr110)

                    COND4_tree = self._adaptor.createWithPayload(COND4)
                    root_0 = self._adaptor.becomeRoot(COND4_tree, root_0)

                    self._state.following.append(self.FOLLOW_addExpr_in_condExpr113)
                    addExpr5 = self.addExpr()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, addExpr5.tree)






                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class conjunction_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def conjunction(self, ):

        retval = self.conjunction_return()
        retval.start = self.input.LT(1)

        root_0 = None

        AND7 = None
        disjunction6 = None

        disjunction8 = None


        AND7_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_disjunction_in_conjunction128)
                disjunction6 = self.disjunction()

                self._state.following.pop()
                self._adaptor.addChild(root_0, disjunction6.tree)

                while True:
                    alt2 = 2
                    LA2_0 = self.input.LA(1)

                    if (LA2_0 == AND) :
                        alt2 = 1


                    if alt2 == 1:

                        pass
                        AND7=self.match(self.input, AND, self.FOLLOW_AND_in_conjunction131)

                        AND7_tree = self._adaptor.createWithPayload(AND7)
                        root_0 = self._adaptor.becomeRoot(AND7_tree, root_0)

                        self._state.following.append(self.FOLLOW_disjunction_in_conjunction134)
                        disjunction8 = self.disjunction()

                        self._state.following.pop()
                        self._adaptor.addChild(root_0, disjunction8.tree)


                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class disjunction_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def disjunction(self, ):

        retval = self.disjunction_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set10 = None
        negation9 = None

        negation11 = None


        set10_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_negation_in_disjunction149)
                negation9 = self.negation()

                self._state.following.pop()
                self._adaptor.addChild(root_0, negation9.tree)

                while True:
                    alt3 = 2
                    LA3_0 = self.input.LA(1)

                    if ((OR <= LA3_0 <= XOR)) :
                        alt3 = 1


                    if alt3 == 1:

                        pass
                        set10 = self.input.LT(1)
                        set10 = self.input.LT(1)
                        if (OR <= self.input.LA(1) <= XOR):
                            self.input.consume()
                            root_0 = self._adaptor.becomeRoot(self._adaptor.createWithPayload(set10), root_0)
                            self._state.errorRecovery = False

                        else:
                            mse = MismatchedSetException(None, self.input)
                            raise mse


                        self._state.following.append(self.FOLLOW_negation_in_disjunction161)
                        negation11 = self.negation()

                        self._state.following.pop()
                        self._adaptor.addChild(root_0, negation11.tree)


                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class negation_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def negation(self, ):

        retval = self.negation_return()
        retval.start = self.input.LT(1)

        root_0 = None

        NOT13 = None
        cmpExpr12 = None

        cmpExpr14 = None


        NOT13_tree = None

        try:
            try:

                alt4 = 2
                LA4_0 = self.input.LA(1)

                if (LA4_0 == MINUS or LA4_0 == LPAREN or LA4_0 == INT or (NAME <= LA4_0 <= PHRASE) or (ABS <= LA4_0 <= SWITCH)) :
                    alt4 = 1
                elif (LA4_0 == NOT) :
                    alt4 = 2
                else:
                    nvae = NoViableAltException("", 4, 0, self.input)

                    raise nvae

                if alt4 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_cmpExpr_in_negation176)
                    cmpExpr12 = self.cmpExpr()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, cmpExpr12.tree)


                elif alt4 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    NOT13=self.match(self.input, NOT, self.FOLLOW_NOT_in_negation182)

                    NOT13_tree = self._adaptor.createWithPayload(NOT13)
                    root_0 = self._adaptor.becomeRoot(NOT13_tree, root_0)

                    self._state.following.append(self.FOLLOW_cmpExpr_in_negation185)
                    cmpExpr14 = self.cmpExpr()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, cmpExpr14.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class cmpExpr_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def cmpExpr(self, ):

        retval = self.cmpExpr_return()
        retval.start = self.input.LT(1)

        root_0 = None

        addExpr15 = None

        cmpOp16 = None

        addExpr17 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_addExpr_in_cmpExpr198)
                addExpr15 = self.addExpr()

                self._state.following.pop()
                self._adaptor.addChild(root_0, addExpr15.tree)

                alt5 = 2
                LA5_0 = self.input.LA(1)

                if ((LT <= LA5_0 <= NE)) :
                    alt5 = 1
                if alt5 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_cmpOp_in_cmpExpr201)
                    cmpOp16 = self.cmpOp()

                    self._state.following.pop()
                    root_0 = self._adaptor.becomeRoot(cmpOp16.tree, root_0)
                    self._state.following.append(self.FOLLOW_addExpr_in_cmpExpr204)
                    addExpr17 = self.addExpr()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, addExpr17.tree)






                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class cmpOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def cmpOp(self, ):

        retval = self.cmpOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set18 = None

        set18_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set18 = self.input.LT(1)
                if (LT <= self.input.LA(1) <= NE):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set18))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class addExpr_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def addExpr(self, ):

        retval = self.addExpr_return()
        retval.start = self.input.LT(1)

        root_0 = None

        multExpr19 = None

        addOp20 = None

        multExpr21 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_multExpr_in_addExpr262)
                multExpr19 = self.multExpr()

                self._state.following.pop()
                self._adaptor.addChild(root_0, multExpr19.tree)

                while True:
                    alt6 = 2
                    LA6_0 = self.input.LA(1)

                    if ((PLUS <= LA6_0 <= MINUS)) :
                        alt6 = 1


                    if alt6 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_addOp_in_addExpr265)
                        addOp20 = self.addOp()

                        self._state.following.pop()
                        root_0 = self._adaptor.becomeRoot(addOp20.tree, root_0)
                        self._state.following.append(self.FOLLOW_multExpr_in_addExpr268)
                        multExpr21 = self.multExpr()

                        self._state.following.pop()
                        self._adaptor.addChild(root_0, multExpr21.tree)


                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class addOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def addOp(self, ):

        retval = self.addOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set22 = None

        set22_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set22 = self.input.LT(1)
                if (PLUS <= self.input.LA(1) <= MINUS):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set22))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class multExpr_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def multExpr(self, ):

        retval = self.multExpr_return()
        retval.start = self.input.LT(1)

        root_0 = None

        unary23 = None

        multOp24 = None

        unary25 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_unary_in_multExpr302)
                unary23 = self.unary()

                self._state.following.pop()
                self._adaptor.addChild(root_0, unary23.tree)

                while True:
                    alt7 = 2
                    LA7_0 = self.input.LA(1)

                    if ((TIMES <= LA7_0 <= DIV)) :
                        alt7 = 1


                    if alt7 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_multOp_in_multExpr305)
                        multOp24 = self.multOp()

                        self._state.following.pop()
                        root_0 = self._adaptor.becomeRoot(multOp24.tree, root_0)
                        self._state.following.append(self.FOLLOW_unary_in_multExpr308)
                        unary25 = self.unary()

                        self._state.following.pop()
                        self._adaptor.addChild(root_0, unary25.tree)


                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class multOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def multOp(self, ):

        retval = self.multOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set26 = None

        set26_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set26 = self.input.LT(1)
                if (TIMES <= self.input.LA(1) <= DIV):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set26))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class unary_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def unary(self, ):

        retval = self.unary_return()
        retval.start = self.input.LT(1)

        root_0 = None

        MINUS27 = None
        atom28 = None

        atom29 = None


        MINUS27_tree = None
        stream_MINUS = RewriteRuleTokenStream(self._adaptor, "token MINUS")
        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        try:
            try:

                alt8 = 2
                LA8_0 = self.input.LA(1)

                if (LA8_0 == MINUS) :
                    alt8 = 1
                elif (LA8_0 == LPAREN or LA8_0 == INT or (NAME <= LA8_0 <= PHRASE) or (ABS <= LA8_0 <= SWITCH)) :
                    alt8 = 2
                else:
                    nvae = NoViableAltException("", 8, 0, self.input)

                    raise nvae

                if alt8 == 1:

                    pass
                    MINUS27=self.match(self.input, MINUS, self.FOLLOW_MINUS_in_unary342)
                    stream_MINUS.add(MINUS27)
                    self._state.following.append(self.FOLLOW_atom_in_unary344)
                    atom28 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom28.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.create(NEG, "-"), root_1)

                    self._adaptor.addChild(root_1, stream_atom.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt8 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_atom_in_unary359)
                    atom29 = self.atom()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, atom29.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class atom_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def atom(self, ):

        retval = self.atom_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LPAREN34 = None
        RPAREN36 = None
        var30 = None

        num31 = None

        str32 = None

        fn33 = None

        conjunction35 = None


        LPAREN34_tree = None
        RPAREN36_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_conjunction = RewriteRuleSubtreeStream(self._adaptor, "rule conjunction")
        try:
            try:

                alt9 = 5
                LA9 = self.input.LA(1)
                if LA9 == NAME:
                    alt9 = 1
                elif LA9 == INT or LA9 == FLOAT:
                    alt9 = 2
                elif LA9 == PHRASE:
                    alt9 = 3
                elif LA9 == ABS or LA9 == COUNT or LA9 == DISTANCE or LA9 == GEOPOINT or LA9 == LEN or LA9 == LOG or LA9 == MAX or LA9 == MIN or LA9 == POW or LA9 == SNIPPET or LA9 == SWITCH:
                    alt9 = 4
                elif LA9 == LPAREN:
                    alt9 = 5
                else:
                    nvae = NoViableAltException("", 9, 0, self.input)

                    raise nvae

                if alt9 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_var_in_atom372)
                    var30 = self.var()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, var30.tree)


                elif alt9 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_num_in_atom378)
                    num31 = self.num()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, num31.tree)


                elif alt9 == 3:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_str_in_atom384)
                    str32 = self.str()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, str32.tree)


                elif alt9 == 4:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_fn_in_atom390)
                    fn33 = self.fn()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, fn33.tree)


                elif alt9 == 5:

                    pass
                    LPAREN34=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_atom396)
                    stream_LPAREN.add(LPAREN34)
                    self._state.following.append(self.FOLLOW_conjunction_in_atom398)
                    conjunction35 = self.conjunction()

                    self._state.following.pop()
                    stream_conjunction.add(conjunction35.tree)
                    RPAREN36=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_atom400)
                    stream_RPAREN.add(RPAREN36)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_conjunction.nextTree())



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class var_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def var(self, ):

        retval = self.var_return()
        retval.start = self.input.LT(1)

        root_0 = None

        name37 = None

        name38 = None

        index39 = None


        stream_index = RewriteRuleSubtreeStream(self._adaptor, "rule index")
        stream_name = RewriteRuleSubtreeStream(self._adaptor, "rule name")
        try:
            try:

                alt10 = 2
                alt10 = self.dfa10.predict(self.input)
                if alt10 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_name_in_var417)
                    name37 = self.name()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, name37.tree)


                elif alt10 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_name_in_var423)
                    name38 = self.name()

                    self._state.following.pop()
                    stream_name.add(name38.tree)
                    self._state.following.append(self.FOLLOW_index_in_var425)
                    index39 = self.index()

                    self._state.following.pop()
                    stream_index.add(index39.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.create(INDEX, ((index39 is not None) and [self.input.toString(index39.start,index39.stop)] or [None])[0]), root_1)

                    self._adaptor.addChild(root_1, stream_name.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class index_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def index(self, ):

        retval = self.index_return()
        retval.start = self.input.LT(1)

        root_0 = None

        x = None
        LSQUARE40 = None
        RSQUARE41 = None

        x_tree = None
        LSQUARE40_tree = None
        RSQUARE41_tree = None
        stream_INT = RewriteRuleTokenStream(self._adaptor, "token INT")
        stream_LSQUARE = RewriteRuleTokenStream(self._adaptor, "token LSQUARE")
        stream_RSQUARE = RewriteRuleTokenStream(self._adaptor, "token RSQUARE")

        try:
            try:


                pass
                LSQUARE40=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_index447)
                stream_LSQUARE.add(LSQUARE40)
                x=self.match(self.input, INT, self.FOLLOW_INT_in_index451)
                stream_INT.add(x)
                RSQUARE41=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_index453)
                stream_RSQUARE.add(RSQUARE41)








                retval.tree = root_0
                stream_x = RewriteRuleTokenStream(self._adaptor, "token x", x)

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()

                self._adaptor.addChild(root_0, stream_x.nextNode())



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class name_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def name(self, ):

        retval = self.name_return()
        retval.start = self.input.LT(1)

        root_0 = None

        NAME42 = None
        char_literal43 = None
        NAME44 = None

        NAME42_tree = None
        char_literal43_tree = None
        NAME44_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                NAME42=self.match(self.input, NAME, self.FOLLOW_NAME_in_name471)

                NAME42_tree = self._adaptor.createWithPayload(NAME42)
                self._adaptor.addChild(root_0, NAME42_tree)


                while True:
                    alt11 = 2
                    LA11_0 = self.input.LA(1)

                    if (LA11_0 == 53) :
                        alt11 = 1


                    if alt11 == 1:

                        pass
                        char_literal43=self.match(self.input, 53, self.FOLLOW_53_in_name474)

                        char_literal43_tree = self._adaptor.createWithPayload(char_literal43)
                        root_0 = self._adaptor.becomeRoot(char_literal43_tree, root_0)

                        NAME44=self.match(self.input, NAME, self.FOLLOW_NAME_in_name477)

                        NAME44_tree = self._adaptor.createWithPayload(NAME44)
                        self._adaptor.addChild(root_0, NAME44_tree)



                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class num_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def num(self, ):

        retval = self.num_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set45 = None

        set45_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set45 = self.input.LT(1)
                if self.input.LA(1) == INT or self.input.LA(1) == FLOAT:
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set45))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class str_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def str(self, ):

        retval = self.str_return()
        retval.start = self.input.LT(1)

        root_0 = None

        PHRASE46 = None

        PHRASE46_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                PHRASE46=self.match(self.input, PHRASE, self.FOLLOW_PHRASE_in_str511)

                PHRASE46_tree = self._adaptor.createWithPayload(PHRASE46)
                self._adaptor.addChild(root_0, PHRASE46_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class fn_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def fn(self, ):

        retval = self.fn_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LPAREN48 = None
        COMMA50 = None
        RPAREN52 = None
        fnName47 = None

        condExpr49 = None

        condExpr51 = None


        LPAREN48_tree = None
        COMMA50_tree = None
        RPAREN52_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_COMMA = RewriteRuleTokenStream(self._adaptor, "token COMMA")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_fnName = RewriteRuleSubtreeStream(self._adaptor, "rule fnName")
        stream_condExpr = RewriteRuleSubtreeStream(self._adaptor, "rule condExpr")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_fnName_in_fn524)
                fnName47 = self.fnName()

                self._state.following.pop()
                stream_fnName.add(fnName47.tree)
                LPAREN48=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_fn526)
                stream_LPAREN.add(LPAREN48)
                self._state.following.append(self.FOLLOW_condExpr_in_fn528)
                condExpr49 = self.condExpr()

                self._state.following.pop()
                stream_condExpr.add(condExpr49.tree)

                while True:
                    alt12 = 2
                    LA12_0 = self.input.LA(1)

                    if (LA12_0 == COMMA) :
                        alt12 = 1


                    if alt12 == 1:

                        pass
                        COMMA50=self.match(self.input, COMMA, self.FOLLOW_COMMA_in_fn531)
                        stream_COMMA.add(COMMA50)
                        self._state.following.append(self.FOLLOW_condExpr_in_fn533)
                        condExpr51 = self.condExpr()

                        self._state.following.pop()
                        stream_condExpr.add(condExpr51.tree)


                    else:
                        break


                RPAREN52=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_fn537)
                stream_RPAREN.add(RPAREN52)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(stream_fnName.nextNode(), root_1)


                if not (stream_condExpr.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_condExpr.hasNext():
                    self._adaptor.addChild(root_1, stream_condExpr.nextTree())


                stream_condExpr.reset()

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval



    class fnName_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def fnName(self, ):

        retval = self.fnName_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set53 = None

        set53_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set53 = self.input.LT(1)
                if (ABS <= self.input.LA(1) <= SWITCH):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set53))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              self.reportError(e)
              raise e
        finally:

            pass

        return retval









    DFA10_eot = DFA.unpack(
        u"\6\uffff"
        )

    DFA10_eof = DFA.unpack(
        u"\1\uffff\1\4\3\uffff\1\4"
        )

    DFA10_min = DFA.unpack(
        u"\1\32\1\6\1\32\2\uffff\1\6"
        )

    DFA10_max = DFA.unpack(
        u"\1\32\1\65\1\32\2\uffff\1\65"
        )

    DFA10_accept = DFA.unpack(
        u"\3\uffff\1\2\1\1\1\uffff"
        )

    DFA10_special = DFA.unpack(
        u"\6\uffff"
        )


    DFA10_transition = [
        DFA.unpack(u"\1\1"),
        DFA.unpack(u"\4\4\1\uffff\12\4\1\uffff\1\4\1\3\5\uffff\1\4\27\uffff"
        u"\1\2"),
        DFA.unpack(u"\1\5"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\4\4\1\uffff\12\4\1\uffff\1\4\1\3\5\uffff\1\4\27\uffff"
        u"\1\2")
    ]



    DFA10 = DFA


    FOLLOW_conjunction_in_expression92 = frozenset([])
    FOLLOW_EOF_in_expression94 = frozenset([1])
    FOLLOW_conjunction_in_condExpr107 = frozenset([1, 6])
    FOLLOW_COND_in_condExpr110 = frozenset([18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_addExpr_in_condExpr113 = frozenset([1])
    FOLLOW_disjunction_in_conjunction128 = frozenset([1, 7])
    FOLLOW_AND_in_conjunction131 = frozenset([10, 18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_disjunction_in_conjunction134 = frozenset([1, 7])
    FOLLOW_negation_in_disjunction149 = frozenset([1, 8, 9])
    FOLLOW_set_in_disjunction152 = frozenset([10, 18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_negation_in_disjunction161 = frozenset([1, 8, 9])
    FOLLOW_cmpExpr_in_negation176 = frozenset([1])
    FOLLOW_NOT_in_negation182 = frozenset([18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_cmpExpr_in_negation185 = frozenset([1])
    FOLLOW_addExpr_in_cmpExpr198 = frozenset([1, 11, 12, 13, 14, 15, 16])
    FOLLOW_cmpOp_in_cmpExpr201 = frozenset([18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_addExpr_in_cmpExpr204 = frozenset([1])
    FOLLOW_set_in_cmpOp0 = frozenset([1])
    FOLLOW_multExpr_in_addExpr262 = frozenset([1, 17, 18])
    FOLLOW_addOp_in_addExpr265 = frozenset([18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_multExpr_in_addExpr268 = frozenset([1, 17, 18])
    FOLLOW_set_in_addOp0 = frozenset([1])
    FOLLOW_unary_in_multExpr302 = frozenset([1, 19, 20])
    FOLLOW_multOp_in_multExpr305 = frozenset([18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_unary_in_multExpr308 = frozenset([1, 19, 20])
    FOLLOW_set_in_multOp0 = frozenset([1])
    FOLLOW_MINUS_in_unary342 = frozenset([18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_atom_in_unary344 = frozenset([1])
    FOLLOW_atom_in_unary359 = frozenset([1])
    FOLLOW_var_in_atom372 = frozenset([1])
    FOLLOW_num_in_atom378 = frozenset([1])
    FOLLOW_str_in_atom384 = frozenset([1])
    FOLLOW_fn_in_atom390 = frozenset([1])
    FOLLOW_LPAREN_in_atom396 = frozenset([10, 18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_conjunction_in_atom398 = frozenset([22])
    FOLLOW_RPAREN_in_atom400 = frozenset([1])
    FOLLOW_name_in_var417 = frozenset([1])
    FOLLOW_name_in_var423 = frozenset([23])
    FOLLOW_index_in_var425 = frozenset([1])
    FOLLOW_LSQUARE_in_index447 = frozenset([24])
    FOLLOW_INT_in_index451 = frozenset([25])
    FOLLOW_RSQUARE_in_index453 = frozenset([1])
    FOLLOW_NAME_in_name471 = frozenset([1, 53])
    FOLLOW_53_in_name474 = frozenset([26])
    FOLLOW_NAME_in_name477 = frozenset([1, 53])
    FOLLOW_set_in_num0 = frozenset([1])
    FOLLOW_PHRASE_in_str511 = frozenset([1])
    FOLLOW_fnName_in_fn524 = frozenset([21])
    FOLLOW_LPAREN_in_fn526 = frozenset([10, 18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_condExpr_in_fn528 = frozenset([22, 29])
    FOLLOW_COMMA_in_fn531 = frozenset([10, 18, 21, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40])
    FOLLOW_condExpr_in_fn533 = frozenset([22, 29])
    FOLLOW_RPAREN_in_fn537 = frozenset([1])
    FOLLOW_set_in_fnName0 = frozenset([1])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import ParserMain
    main = ParserMain("ExpressionLexer", ExpressionParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
