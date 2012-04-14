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


DOLLAR=31
LT=7
EXPONENT=26
LSQUARE=19
ASCII_LETTER=29
FLOAT=23
NAME_START=27
EOF=-1
LPAREN=17
INDEX=5
RPAREN=18
NAME=22
PLUS=13
DIGIT=25
EQ=11
NE=12
T__42=42
T__43=43
T__40=40
GE=10
T__41=41
T__44=44
UNDERSCORE=30
INT=20
FN=6
MINUS=14
RSQUARE=21
PHRASE=24
T__32=32
T__33=33
WS=28
T__34=34
T__35=35
T__36=36
T__37=37
T__38=38
T__39=39
NEG=4
GT=9
DIV=16
TIMES=15
LE=8


tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "NEG", "INDEX", "FN", "LT", "LE", "GT", "GE", "EQ", "NE", "PLUS", "MINUS",
    "TIMES", "DIV", "LPAREN", "RPAREN", "LSQUARE", "INT", "RSQUARE", "NAME",
    "FLOAT", "PHRASE", "DIGIT", "EXPONENT", "NAME_START", "WS", "ASCII_LETTER",
    "UNDERSCORE", "DOLLAR", "'.'", "','", "'abs'", "'count'", "'if'", "'kilometers'",
    "'len'", "'log'", "'max'", "'miles'", "'min'", "'pow'", "'snippet'"
]




class ExpressionParser(Parser):
    grammarFileName = "blaze-out/host/genfiles/apphosting/api/search/genantlr/Expression.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"
    tokenNames = tokenNames

    def __init__(self, input, state=None):
        if state is None:
            state = RecognizerSharedState()

        Parser.__init__(self, input, state)


        self.dfa6 = self.DFA6(
            self, 6,
            eot = self.DFA6_eot,
            eof = self.DFA6_eof,
            min = self.DFA6_min,
            max = self.DFA6_max,
            accept = self.DFA6_accept,
            special = self.DFA6_special,
            transition = self.DFA6_transition
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
        cmpExpr1 = None


        EOF2_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_cmpExpr_in_expression92)
                cmpExpr1 = self.cmpExpr()

                self._state.following.pop()
                self._adaptor.addChild(root_0, cmpExpr1.tree)
                EOF2=self.match(self.input, EOF, self.FOLLOW_EOF_in_expression94)

                EOF2_tree = self._adaptor.createWithPayload(EOF2)
                self._adaptor.addChild(root_0, EOF2_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        addExpr3 = None

        cmpOp4 = None

        addExpr5 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_addExpr_in_cmpExpr107)
                addExpr3 = self.addExpr()

                self._state.following.pop()
                self._adaptor.addChild(root_0, addExpr3.tree)

                alt1 = 2
                LA1_0 = self.input.LA(1)

                if ((LT <= LA1_0 <= NE)) :
                    alt1 = 1
                if alt1 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_cmpOp_in_cmpExpr110)
                    cmpOp4 = self.cmpOp()

                    self._state.following.pop()
                    root_0 = self._adaptor.becomeRoot(cmpOp4.tree, root_0)
                    self._state.following.append(self.FOLLOW_addExpr_in_cmpExpr113)
                    addExpr5 = self.addExpr()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, addExpr5.tree)






                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        set6 = None

        set6_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set6 = self.input.LT(1)
                if (LT <= self.input.LA(1) <= NE):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set6))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        multExpr7 = None

        addOp8 = None

        multExpr9 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_multExpr_in_addExpr171)
                multExpr7 = self.multExpr()

                self._state.following.pop()
                self._adaptor.addChild(root_0, multExpr7.tree)

                while True:
                    alt2 = 2
                    LA2_0 = self.input.LA(1)

                    if ((PLUS <= LA2_0 <= MINUS)) :
                        alt2 = 1


                    if alt2 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_addOp_in_addExpr174)
                        addOp8 = self.addOp()

                        self._state.following.pop()
                        root_0 = self._adaptor.becomeRoot(addOp8.tree, root_0)
                        self._state.following.append(self.FOLLOW_multExpr_in_addExpr177)
                        multExpr9 = self.multExpr()

                        self._state.following.pop()
                        self._adaptor.addChild(root_0, multExpr9.tree)


                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        set10 = None

        set10_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set10 = self.input.LT(1)
                if (PLUS <= self.input.LA(1) <= MINUS):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set10))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        unary11 = None

        multOp12 = None

        unary13 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_unary_in_multExpr211)
                unary11 = self.unary()

                self._state.following.pop()
                self._adaptor.addChild(root_0, unary11.tree)

                while True:
                    alt3 = 2
                    LA3_0 = self.input.LA(1)

                    if ((TIMES <= LA3_0 <= DIV)) :
                        alt3 = 1


                    if alt3 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_multOp_in_multExpr214)
                        multOp12 = self.multOp()

                        self._state.following.pop()
                        root_0 = self._adaptor.becomeRoot(multOp12.tree, root_0)
                        self._state.following.append(self.FOLLOW_unary_in_multExpr217)
                        unary13 = self.unary()

                        self._state.following.pop()
                        self._adaptor.addChild(root_0, unary13.tree)


                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        set14 = None

        set14_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set14 = self.input.LT(1)
                if (TIMES <= self.input.LA(1) <= DIV):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set14))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        MINUS15 = None
        atom16 = None

        atom17 = None


        MINUS15_tree = None
        stream_MINUS = RewriteRuleTokenStream(self._adaptor, "token MINUS")
        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        try:
            try:

                alt4 = 2
                LA4_0 = self.input.LA(1)

                if (LA4_0 == MINUS) :
                    alt4 = 1
                elif (LA4_0 == LPAREN or LA4_0 == INT or (NAME <= LA4_0 <= PHRASE) or (34 <= LA4_0 <= 44)) :
                    alt4 = 2
                else:
                    nvae = NoViableAltException("", 4, 0, self.input)

                    raise nvae

                if alt4 == 1:

                    pass
                    MINUS15=self.match(self.input, MINUS, self.FOLLOW_MINUS_in_unary251)
                    stream_MINUS.add(MINUS15)
                    self._state.following.append(self.FOLLOW_atom_in_unary253)
                    atom16 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom16.tree)








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


                elif alt4 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_atom_in_unary268)
                    atom17 = self.atom()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, atom17.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        LPAREN22 = None
        RPAREN24 = None
        var18 = None

        num19 = None

        str20 = None

        fn21 = None

        addExpr23 = None


        LPAREN22_tree = None
        RPAREN24_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_addExpr = RewriteRuleSubtreeStream(self._adaptor, "rule addExpr")
        try:
            try:

                alt5 = 5
                LA5 = self.input.LA(1)
                if LA5 == NAME:
                    alt5 = 1
                elif LA5 == INT or LA5 == FLOAT:
                    alt5 = 2
                elif LA5 == PHRASE:
                    alt5 = 3
                elif LA5 == 34 or LA5 == 35 or LA5 == 36 or LA5 == 37 or LA5 == 38 or LA5 == 39 or LA5 == 40 or LA5 == 41 or LA5 == 42 or LA5 == 43 or LA5 == 44:
                    alt5 = 4
                elif LA5 == LPAREN:
                    alt5 = 5
                else:
                    nvae = NoViableAltException("", 5, 0, self.input)

                    raise nvae

                if alt5 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_var_in_atom281)
                    var18 = self.var()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, var18.tree)


                elif alt5 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_num_in_atom287)
                    num19 = self.num()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, num19.tree)


                elif alt5 == 3:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_str_in_atom293)
                    str20 = self.str()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, str20.tree)


                elif alt5 == 4:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_fn_in_atom299)
                    fn21 = self.fn()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, fn21.tree)


                elif alt5 == 5:

                    pass
                    LPAREN22=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_atom305)
                    stream_LPAREN.add(LPAREN22)
                    self._state.following.append(self.FOLLOW_addExpr_in_atom307)
                    addExpr23 = self.addExpr()

                    self._state.following.pop()
                    stream_addExpr.add(addExpr23.tree)
                    RPAREN24=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_atom309)
                    stream_RPAREN.add(RPAREN24)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_addExpr.nextTree())



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        name25 = None

        name26 = None

        index27 = None


        stream_index = RewriteRuleSubtreeStream(self._adaptor, "rule index")
        stream_name = RewriteRuleSubtreeStream(self._adaptor, "rule name")
        try:
            try:

                alt6 = 2
                alt6 = self.dfa6.predict(self.input)
                if alt6 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_name_in_var326)
                    name25 = self.name()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, name25.tree)


                elif alt6 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_name_in_var332)
                    name26 = self.name()

                    self._state.following.pop()
                    stream_name.add(name26.tree)
                    self._state.following.append(self.FOLLOW_index_in_var334)
                    index27 = self.index()

                    self._state.following.pop()
                    stream_index.add(index27.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.create(INDEX, ((index27 is not None) and [self.input.toString(index27.start,index27.stop)] or [None])[0]), root_1)

                    self._adaptor.addChild(root_1, stream_name.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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
        LSQUARE28 = None
        RSQUARE29 = None

        x_tree = None
        LSQUARE28_tree = None
        RSQUARE29_tree = None
        stream_INT = RewriteRuleTokenStream(self._adaptor, "token INT")
        stream_LSQUARE = RewriteRuleTokenStream(self._adaptor, "token LSQUARE")
        stream_RSQUARE = RewriteRuleTokenStream(self._adaptor, "token RSQUARE")

        try:
            try:


                pass
                LSQUARE28=self.match(self.input, LSQUARE, self.FOLLOW_LSQUARE_in_index356)
                stream_LSQUARE.add(LSQUARE28)
                x=self.match(self.input, INT, self.FOLLOW_INT_in_index360)
                stream_INT.add(x)
                RSQUARE29=self.match(self.input, RSQUARE, self.FOLLOW_RSQUARE_in_index362)
                stream_RSQUARE.add(RSQUARE29)








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
              reportError(e)
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

        NAME30 = None
        char_literal31 = None
        NAME32 = None

        NAME30_tree = None
        char_literal31_tree = None
        NAME32_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                NAME30=self.match(self.input, NAME, self.FOLLOW_NAME_in_name380)

                NAME30_tree = self._adaptor.createWithPayload(NAME30)
                self._adaptor.addChild(root_0, NAME30_tree)


                while True:
                    alt7 = 2
                    LA7_0 = self.input.LA(1)

                    if (LA7_0 == 32) :
                        alt7 = 1


                    if alt7 == 1:

                        pass
                        char_literal31=self.match(self.input, 32, self.FOLLOW_32_in_name383)

                        char_literal31_tree = self._adaptor.createWithPayload(char_literal31)
                        root_0 = self._adaptor.becomeRoot(char_literal31_tree, root_0)

                        NAME32=self.match(self.input, NAME, self.FOLLOW_NAME_in_name386)

                        NAME32_tree = self._adaptor.createWithPayload(NAME32)
                        self._adaptor.addChild(root_0, NAME32_tree)



                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        set33 = None

        set33_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set33 = self.input.LT(1)
                if self.input.LA(1) == INT or self.input.LA(1) == FLOAT:
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set33))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        PHRASE34 = None

        PHRASE34_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                PHRASE34=self.match(self.input, PHRASE, self.FOLLOW_PHRASE_in_str420)

                PHRASE34_tree = self._adaptor.createWithPayload(PHRASE34)
                self._adaptor.addChild(root_0, PHRASE34_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        LPAREN36 = None
        char_literal38 = None
        RPAREN40 = None
        fnName35 = None

        cmpExpr37 = None

        cmpExpr39 = None


        LPAREN36_tree = None
        char_literal38_tree = None
        RPAREN40_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_33 = RewriteRuleTokenStream(self._adaptor, "token 33")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_fnName = RewriteRuleSubtreeStream(self._adaptor, "rule fnName")
        stream_cmpExpr = RewriteRuleSubtreeStream(self._adaptor, "rule cmpExpr")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_fnName_in_fn433)
                fnName35 = self.fnName()

                self._state.following.pop()
                stream_fnName.add(fnName35.tree)
                LPAREN36=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_fn435)
                stream_LPAREN.add(LPAREN36)
                self._state.following.append(self.FOLLOW_cmpExpr_in_fn437)
                cmpExpr37 = self.cmpExpr()

                self._state.following.pop()
                stream_cmpExpr.add(cmpExpr37.tree)

                while True:
                    alt8 = 2
                    LA8_0 = self.input.LA(1)

                    if (LA8_0 == 33) :
                        alt8 = 1


                    if alt8 == 1:

                        pass
                        char_literal38=self.match(self.input, 33, self.FOLLOW_33_in_fn440)
                        stream_33.add(char_literal38)
                        self._state.following.append(self.FOLLOW_cmpExpr_in_fn442)
                        cmpExpr39 = self.cmpExpr()

                        self._state.following.pop()
                        stream_cmpExpr.add(cmpExpr39.tree)


                    else:
                        break


                RPAREN40=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_fn446)
                stream_RPAREN.add(RPAREN40)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.create(FN, ((fnName35 is not None) and [self.input.toString(fnName35.start,fnName35.stop)] or [None])[0]), root_1)


                if not (stream_cmpExpr.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_cmpExpr.hasNext():
                    self._adaptor.addChild(root_1, stream_cmpExpr.nextTree())


                stream_cmpExpr.reset()

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
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

        set41 = None

        set41_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set41 = self.input.LT(1)
                if (34 <= self.input.LA(1) <= 44):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set41))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)



            except RecognitionException, e:
              reportError(e)
              raise e
        finally:

            pass

        return retval









    DFA6_eot = DFA.unpack(
        u"\6\uffff"
        )

    DFA6_eof = DFA.unpack(
        u"\1\uffff\1\4\3\uffff\1\4"
        )

    DFA6_min = DFA.unpack(
        u"\1\26\1\7\1\26\2\uffff\1\7"
        )

    DFA6_max = DFA.unpack(
        u"\1\26\1\41\1\26\2\uffff\1\41"
        )

    DFA6_accept = DFA.unpack(
        u"\3\uffff\1\2\1\1\1\uffff"
        )

    DFA6_special = DFA.unpack(
        u"\6\uffff"
        )


    DFA6_transition = [
        DFA.unpack(u"\1\1"),
        DFA.unpack(u"\12\4\1\uffff\1\4\1\3\14\uffff\1\2\1\4"),
        DFA.unpack(u"\1\5"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\12\4\1\uffff\1\4\1\3\14\uffff\1\2\1\4")
    ]



    DFA6 = DFA


    FOLLOW_cmpExpr_in_expression92 = frozenset([])
    FOLLOW_EOF_in_expression94 = frozenset([1])
    FOLLOW_addExpr_in_cmpExpr107 = frozenset([1, 7, 8, 9, 10, 11, 12])
    FOLLOW_cmpOp_in_cmpExpr110 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_addExpr_in_cmpExpr113 = frozenset([1])
    FOLLOW_set_in_cmpOp0 = frozenset([1])
    FOLLOW_multExpr_in_addExpr171 = frozenset([1, 13, 14])
    FOLLOW_addOp_in_addExpr174 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_multExpr_in_addExpr177 = frozenset([1, 13, 14])
    FOLLOW_set_in_addOp0 = frozenset([1])
    FOLLOW_unary_in_multExpr211 = frozenset([1, 15, 16])
    FOLLOW_multOp_in_multExpr214 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_unary_in_multExpr217 = frozenset([1, 15, 16])
    FOLLOW_set_in_multOp0 = frozenset([1])
    FOLLOW_MINUS_in_unary251 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_atom_in_unary253 = frozenset([1])
    FOLLOW_atom_in_unary268 = frozenset([1])
    FOLLOW_var_in_atom281 = frozenset([1])
    FOLLOW_num_in_atom287 = frozenset([1])
    FOLLOW_str_in_atom293 = frozenset([1])
    FOLLOW_fn_in_atom299 = frozenset([1])
    FOLLOW_LPAREN_in_atom305 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_addExpr_in_atom307 = frozenset([18])
    FOLLOW_RPAREN_in_atom309 = frozenset([1])
    FOLLOW_name_in_var326 = frozenset([1])
    FOLLOW_name_in_var332 = frozenset([19])
    FOLLOW_index_in_var334 = frozenset([1])
    FOLLOW_LSQUARE_in_index356 = frozenset([20])
    FOLLOW_INT_in_index360 = frozenset([21])
    FOLLOW_RSQUARE_in_index362 = frozenset([1])
    FOLLOW_NAME_in_name380 = frozenset([1, 32])
    FOLLOW_32_in_name383 = frozenset([22])
    FOLLOW_NAME_in_name386 = frozenset([1, 32])
    FOLLOW_set_in_num0 = frozenset([1])
    FOLLOW_PHRASE_in_str420 = frozenset([1])
    FOLLOW_fnName_in_fn433 = frozenset([17])
    FOLLOW_LPAREN_in_fn435 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_cmpExpr_in_fn437 = frozenset([18, 33])
    FOLLOW_33_in_fn440 = frozenset([14, 17, 20, 22, 23, 24, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_cmpExpr_in_fn442 = frozenset([18, 33])
    FOLLOW_RPAREN_in_fn446 = frozenset([1])
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
