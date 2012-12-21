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


FUNCTION=7
LT=19
EXPONENT=37
LETTER=42
OCTAL_ESC=46
FUZZY=8
FLOAT=27
NAME_START=39
NOT=34
AND=32
EOF=-1
LPAREN=25
WORD=15
HAS=24
RPAREN=26
NAME=29
ESC_SEQ=38
ARGS=4
DIGIT=35
EQ=23
DOT=36
NE=22
GE=20
T__47=47
T__48=48
T__49=49
CONJUNCTION=5
UNICODE_ESC=45
NAME_MID=40
NUMBER=12
HEX_DIGIT=44
UNDERSCORE=43
LITERAL=9
INT=28
VALUE=16
TEXT=31
PHRASE=30
RESTRICTION=13
DISJUNCTION=6
WS=17
NEGATION=10
NEG=41
OR=33
GT=21
GLOBAL=11
LE=18
STRING=14


tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "ARGS", "CONJUNCTION", "DISJUNCTION", "FUNCTION", "FUZZY", "LITERAL",
    "NEGATION", "GLOBAL", "NUMBER", "RESTRICTION", "STRING", "WORD", "VALUE",
    "WS", "LE", "LT", "GE", "GT", "NE", "EQ", "HAS", "LPAREN", "RPAREN",
    "FLOAT", "INT", "NAME", "PHRASE", "TEXT", "AND", "OR", "NOT", "DIGIT",
    "DOT", "EXPONENT", "ESC_SEQ", "NAME_START", "NAME_MID", "NEG", "LETTER",
    "UNDERSCORE", "HEX_DIGIT", "UNICODE_ESC", "OCTAL_ESC", "'+'", "'~'",
    "','"
]




class QueryParser(Parser):
    grammarFileName = ""
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"
    tokenNames = tokenNames

    def __init__(self, input, state=None):
        if state is None:
            state = RecognizerSharedState()

        Parser.__init__(self, input, state)


        self.dfa2 = self.DFA2(
            self, 2,
            eot = self.DFA2_eot,
            eof = self.DFA2_eof,
            min = self.DFA2_min,
            max = self.DFA2_max,
            accept = self.DFA2_accept,
            special = self.DFA2_special,
            transition = self.DFA2_transition
            )

        self.dfa4 = self.DFA4(
            self, 4,
            eot = self.DFA4_eot,
            eof = self.DFA4_eof,
            min = self.DFA4_min,
            max = self.DFA4_max,
            accept = self.DFA4_accept,
            special = self.DFA4_special,
            transition = self.DFA4_transition
            )

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


    class query_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def query(self, ):

        retval = self.query_return()
        retval.start = self.input.LT(1)

        root_0 = None

        EOF2 = None
        expression1 = None


        EOF2_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_expression_in_query122)
                expression1 = self.expression()

                self._state.following.pop()
                self._adaptor.addChild(root_0, expression1.tree)
                EOF2=self.match(self.input, EOF, self.FOLLOW_EOF_in_query124)

                EOF2_tree = self._adaptor.createWithPayload(EOF2)
                self._adaptor.addChild(root_0, EOF2_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class expression_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def expression(self, ):

        retval = self.expression_return()
        retval.start = self.input.LT(1)

        root_0 = None

        WS3 = None
        WS7 = None
        factor4 = None

        andOp5 = None

        factor6 = None


        WS3_tree = None
        WS7_tree = None
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_factor = RewriteRuleSubtreeStream(self._adaptor, "rule factor")
        stream_andOp = RewriteRuleSubtreeStream(self._adaptor, "rule andOp")
        try:
            try:


                pass

                while True:
                    alt1 = 2
                    LA1_0 = self.input.LA(1)

                    if (LA1_0 == WS) :
                        alt1 = 1


                    if alt1 == 1:

                        pass
                        WS3=self.match(self.input, WS, self.FOLLOW_WS_in_expression142)
                        stream_WS.add(WS3)


                    else:
                        break


                self._state.following.append(self.FOLLOW_factor_in_expression145)
                factor4 = self.factor()

                self._state.following.pop()
                stream_factor.add(factor4.tree)

                while True:
                    alt2 = 2
                    alt2 = self.dfa2.predict(self.input)
                    if alt2 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_andOp_in_expression148)
                        andOp5 = self.andOp()

                        self._state.following.pop()
                        stream_andOp.add(andOp5.tree)
                        self._state.following.append(self.FOLLOW_factor_in_expression150)
                        factor6 = self.factor()

                        self._state.following.pop()
                        stream_factor.add(factor6.tree)


                    else:
                        break



                while True:
                    alt3 = 2
                    LA3_0 = self.input.LA(1)

                    if (LA3_0 == WS) :
                        alt3 = 1


                    if alt3 == 1:

                        pass
                        WS7=self.match(self.input, WS, self.FOLLOW_WS_in_expression154)
                        stream_WS.add(WS7)


                    else:
                        break










                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(CONJUNCTION, "CONJUNCTION"), root_1)


                if not (stream_factor.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_factor.hasNext():
                    self._adaptor.addChild(root_1, stream_factor.nextTree())


                stream_factor.reset()

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class factor_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def factor(self, ):

        retval = self.factor_return()
        retval.start = self.input.LT(1)

        root_0 = None

        term8 = None

        orOp9 = None

        term10 = None


        stream_orOp = RewriteRuleSubtreeStream(self._adaptor, "rule orOp")
        stream_term = RewriteRuleSubtreeStream(self._adaptor, "rule term")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_term_in_factor181)
                term8 = self.term()

                self._state.following.pop()
                stream_term.add(term8.tree)

                while True:
                    alt4 = 2
                    alt4 = self.dfa4.predict(self.input)
                    if alt4 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_orOp_in_factor184)
                        orOp9 = self.orOp()

                        self._state.following.pop()
                        stream_orOp.add(orOp9.tree)
                        self._state.following.append(self.FOLLOW_term_in_factor186)
                        term10 = self.term()

                        self._state.following.pop()
                        stream_term.add(term10.tree)


                    else:
                        break










                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(DISJUNCTION, "DISJUNCTION"), root_1)


                if not (stream_term.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_term.hasNext():
                    self._adaptor.addChild(root_1, stream_term.nextTree())


                stream_term.reset()

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class term_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def term(self, ):

        retval = self.term_return()
        retval.start = self.input.LT(1)

        root_0 = None

        notOp11 = None

        primitive12 = None

        primitive13 = None


        stream_notOp = RewriteRuleSubtreeStream(self._adaptor, "rule notOp")
        stream_primitive = RewriteRuleSubtreeStream(self._adaptor, "rule primitive")
        try:
            try:

                alt5 = 2
                LA5_0 = self.input.LA(1)

                if (LA5_0 == NOT or LA5_0 == NEG) :
                    alt5 = 1
                elif (LA5_0 == LPAREN or (FLOAT <= LA5_0 <= TEXT) or (47 <= LA5_0 <= 48)) :
                    alt5 = 2
                else:
                    nvae = NoViableAltException("", 5, 0, self.input)

                    raise nvae

                if alt5 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_notOp_in_term215)
                    notOp11 = self.notOp()

                    self._state.following.pop()
                    stream_notOp.add(notOp11.tree)
                    self._state.following.append(self.FOLLOW_primitive_in_term217)
                    primitive12 = self.primitive()

                    self._state.following.pop()
                    stream_primitive.add(primitive12.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(NEGATION, "NEGATION"), root_1)

                    self._adaptor.addChild(root_1, stream_primitive.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt5 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_primitive_in_term231)
                    primitive13 = self.primitive()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, primitive13.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class primitive_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def primitive(self, ):

        retval = self.primitive_return()
        retval.start = self.input.LT(1)

        root_0 = None

        restrict14 = None

        atom15 = None


        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        try:
            try:

                alt6 = 2
                alt6 = self.dfa6.predict(self.input)
                if alt6 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_restrict_in_primitive250)
                    restrict14 = self.restrict()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, restrict14.tree)


                elif alt6 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_atom_in_primitive256)
                    atom15 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom15.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(GLOBAL, "GLOBAL"))

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(EQ, "EQ"), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class restrict_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def restrict(self, ):

        retval = self.restrict_return()
        retval.start = self.input.LT(1)

        root_0 = None

        simple16 = None

        comparator17 = None

        atom18 = None


        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        stream_simple = RewriteRuleSubtreeStream(self._adaptor, "rule simple")
        stream_comparator = RewriteRuleSubtreeStream(self._adaptor, "rule comparator")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_simple_in_restrict283)
                simple16 = self.simple()

                self._state.following.pop()
                stream_simple.add(simple16.tree)
                self._state.following.append(self.FOLLOW_comparator_in_restrict285)
                comparator17 = self.comparator()

                self._state.following.pop()
                stream_comparator.add(comparator17.tree)
                self._state.following.append(self.FOLLOW_atom_in_restrict287)
                atom18 = self.atom()

                self._state.following.pop()
                stream_atom.add(atom18.tree)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                self._adaptor.addChild(root_1, stream_simple.nextTree())

                root_2 = self._adaptor.nil()
                root_2 = self._adaptor.becomeRoot(stream_comparator.nextNode(), root_2)

                self._adaptor.addChild(root_2, stream_atom.nextTree())

                self._adaptor.addChild(root_1, root_2)

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class comparator_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def comparator(self, ):

        retval = self.comparator_return()
        retval.start = self.input.LT(1)

        root_0 = None

        x = None
        WS19 = None
        WS20 = None

        x_tree = None
        WS19_tree = None
        WS20_tree = None
        stream_HAS = RewriteRuleTokenStream(self._adaptor, "token HAS")
        stream_GE = RewriteRuleTokenStream(self._adaptor, "token GE")
        stream_GT = RewriteRuleTokenStream(self._adaptor, "token GT")
        stream_LT = RewriteRuleTokenStream(self._adaptor, "token LT")
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_EQ = RewriteRuleTokenStream(self._adaptor, "token EQ")
        stream_LE = RewriteRuleTokenStream(self._adaptor, "token LE")
        stream_NE = RewriteRuleTokenStream(self._adaptor, "token NE")

        try:
            try:


                pass

                while True:
                    alt7 = 2
                    LA7_0 = self.input.LA(1)

                    if (LA7_0 == WS) :
                        alt7 = 1


                    if alt7 == 1:

                        pass
                        WS19=self.match(self.input, WS, self.FOLLOW_WS_in_comparator314)
                        stream_WS.add(WS19)


                    else:
                        break



                alt8 = 7
                LA8 = self.input.LA(1)
                if LA8 == LE:
                    alt8 = 1
                elif LA8 == LT:
                    alt8 = 2
                elif LA8 == GE:
                    alt8 = 3
                elif LA8 == GT:
                    alt8 = 4
                elif LA8 == NE:
                    alt8 = 5
                elif LA8 == EQ:
                    alt8 = 6
                elif LA8 == HAS:
                    alt8 = 7
                else:
                    nvae = NoViableAltException("", 8, 0, self.input)

                    raise nvae

                if alt8 == 1:

                    pass
                    x=self.match(self.input, LE, self.FOLLOW_LE_in_comparator320)
                    stream_LE.add(x)


                elif alt8 == 2:

                    pass
                    x=self.match(self.input, LT, self.FOLLOW_LT_in_comparator326)
                    stream_LT.add(x)


                elif alt8 == 3:

                    pass
                    x=self.match(self.input, GE, self.FOLLOW_GE_in_comparator332)
                    stream_GE.add(x)


                elif alt8 == 4:

                    pass
                    x=self.match(self.input, GT, self.FOLLOW_GT_in_comparator338)
                    stream_GT.add(x)


                elif alt8 == 5:

                    pass
                    x=self.match(self.input, NE, self.FOLLOW_NE_in_comparator344)
                    stream_NE.add(x)


                elif alt8 == 6:

                    pass
                    x=self.match(self.input, EQ, self.FOLLOW_EQ_in_comparator350)
                    stream_EQ.add(x)


                elif alt8 == 7:

                    pass
                    x=self.match(self.input, HAS, self.FOLLOW_HAS_in_comparator356)
                    stream_HAS.add(x)




                while True:
                    alt9 = 2
                    LA9_0 = self.input.LA(1)

                    if (LA9_0 == WS) :
                        alt9 = 1


                    if alt9 == 1:

                        pass
                        WS20=self.match(self.input, WS, self.FOLLOW_WS_in_comparator359)
                        stream_WS.add(WS20)


                    else:
                        break










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


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
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
        value21 = None

        expression23 = None


        LPAREN22_tree = None
        RPAREN24_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_expression = RewriteRuleSubtreeStream(self._adaptor, "rule expression")
        try:
            try:

                alt10 = 2
                LA10_0 = self.input.LA(1)

                if ((FLOAT <= LA10_0 <= TEXT) or (47 <= LA10_0 <= 48)) :
                    alt10 = 1
                elif (LA10_0 == LPAREN) :
                    alt10 = 2
                else:
                    nvae = NoViableAltException("", 10, 0, self.input)

                    raise nvae

                if alt10 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_value_in_atom378)
                    value21 = self.value()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, value21.tree)


                elif alt10 == 2:

                    pass
                    LPAREN22=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_atom384)
                    stream_LPAREN.add(LPAREN22)
                    self._state.following.append(self.FOLLOW_expression_in_atom386)
                    expression23 = self.expression()

                    self._state.following.pop()
                    stream_expression.add(expression23.tree)
                    RPAREN24=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_atom388)
                    stream_RPAREN.add(RPAREN24)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_expression.nextTree())



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class value_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def value(self, ):

        retval = self.value_return()
        retval.start = self.input.LT(1)

        root_0 = None

        text_value25 = None

        numeric_value26 = None


        stream_numeric_value = RewriteRuleSubtreeStream(self._adaptor, "rule numeric_value")
        try:
            try:

                alt11 = 2
                LA11_0 = self.input.LA(1)

                if ((NAME <= LA11_0 <= TEXT) or (47 <= LA11_0 <= 48)) :
                    alt11 = 1
                elif ((FLOAT <= LA11_0 <= INT)) :
                    alt11 = 2
                else:
                    nvae = NoViableAltException("", 11, 0, self.input)

                    raise nvae

                if alt11 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_text_value_in_value405)
                    text_value25 = self.text_value()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, text_value25.tree)


                elif alt11 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_numeric_value_in_value411)
                    numeric_value26 = self.numeric_value()

                    self._state.following.pop()
                    stream_numeric_value.add(numeric_value26.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(NUMBER, "NUMBER"))
                    self._adaptor.addChild(root_1, stream_numeric_value.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class numeric_value_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def numeric_value(self, ):

        retval = self.numeric_value_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set27 = None

        set27_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set27 = self.input.LT(1)
                if (FLOAT <= self.input.LA(1) <= INT):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set27))
                    self._state.errorRecovery = False

                else:
                    mse = MismatchedSetException(None, self.input)
                    raise mse





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class text_value_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def text_value(self, ):

        retval = self.text_value_return()
        retval.start = self.input.LT(1)

        root_0 = None

        literal_text28 = None

        rewritable_text29 = None

        text30 = None



        try:
            try:

                alt12 = 3
                LA12 = self.input.LA(1)
                if LA12 == 47:
                    alt12 = 1
                elif LA12 == 48:
                    alt12 = 2
                elif LA12 == NAME or LA12 == PHRASE or LA12 == TEXT:
                    alt12 = 3
                else:
                    nvae = NoViableAltException("", 12, 0, self.input)

                    raise nvae

                if alt12 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_literal_text_in_text_value453)
                    literal_text28 = self.literal_text()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, literal_text28.tree)


                elif alt12 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_rewritable_text_in_text_value459)
                    rewritable_text29 = self.rewritable_text()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, rewritable_text29.tree)


                elif alt12 == 3:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_text_in_text_value465)
                    text30 = self.text()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, text30.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class literal_text_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def literal_text(self, ):

        retval = self.literal_text_return()
        retval.start = self.input.LT(1)

        root_0 = None

        char_literal31 = None
        text32 = None


        char_literal31_tree = None
        stream_47 = RewriteRuleTokenStream(self._adaptor, "token 47")
        stream_text = RewriteRuleSubtreeStream(self._adaptor, "rule text")
        try:
            try:


                pass
                char_literal31=self.match(self.input, 47, self.FOLLOW_47_in_literal_text478)
                stream_47.add(char_literal31)
                self._state.following.append(self.FOLLOW_text_in_literal_text480)
                text32 = self.text()

                self._state.following.pop()
                stream_text.add(text32.tree)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(LITERAL, "LITERAL"), root_1)

                self._adaptor.addChild(root_1, stream_text.nextTree())

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class rewritable_text_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def rewritable_text(self, ):

        retval = self.rewritable_text_return()
        retval.start = self.input.LT(1)

        root_0 = None

        char_literal33 = None
        text34 = None


        char_literal33_tree = None
        stream_48 = RewriteRuleTokenStream(self._adaptor, "token 48")
        stream_text = RewriteRuleSubtreeStream(self._adaptor, "rule text")
        try:
            try:


                pass
                char_literal33=self.match(self.input, 48, self.FOLLOW_48_in_rewritable_text500)
                stream_48.add(char_literal33)
                self._state.following.append(self.FOLLOW_text_in_rewritable_text502)
                text34 = self.text()

                self._state.following.pop()
                stream_text.add(text34.tree)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(FUZZY, "FUZZY"), root_1)

                self._adaptor.addChild(root_1, stream_text.nextTree())

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class text_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def text(self, ):

        retval = self.text_return()
        retval.start = self.input.LT(1)

        root_0 = None

        n = None
        s = None
        t = None

        n_tree = None
        s_tree = None
        t_tree = None
        stream_NAME = RewriteRuleTokenStream(self._adaptor, "token NAME")
        stream_TEXT = RewriteRuleTokenStream(self._adaptor, "token TEXT")
        stream_PHRASE = RewriteRuleTokenStream(self._adaptor, "token PHRASE")

        try:
            try:

                alt13 = 3
                LA13 = self.input.LA(1)
                if LA13 == NAME:
                    alt13 = 1
                elif LA13 == PHRASE:
                    alt13 = 2
                elif LA13 == TEXT:
                    alt13 = 3
                else:
                    nvae = NoViableAltException("", 13, 0, self.input)

                    raise nvae

                if alt13 == 1:

                    pass
                    n=self.match(self.input, NAME, self.FOLLOW_NAME_in_text524)
                    stream_NAME.add(n)








                    retval.tree = root_0
                    stream_n = RewriteRuleTokenStream(self._adaptor, "token n", n)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(WORD, "WORD"))
                    self._adaptor.addChild(root_1, stream_n.nextNode())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt13 == 2:

                    pass
                    s=self.match(self.input, PHRASE, self.FOLLOW_PHRASE_in_text543)
                    stream_PHRASE.add(s)








                    retval.tree = root_0
                    stream_s = RewriteRuleTokenStream(self._adaptor, "token s", s)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(STRING, "STRING"))
                    self._adaptor.addChild(root_1, stream_s.nextNode())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt13 == 3:

                    pass
                    t=self.match(self.input, TEXT, self.FOLLOW_TEXT_in_text562)
                    stream_TEXT.add(t)








                    retval.tree = root_0
                    stream_t = RewriteRuleTokenStream(self._adaptor, "token t", t)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(WORD, "WORD"))
                    self._adaptor.addChild(root_1, stream_t.nextNode())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class simple_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def simple(self, ):

        retval = self.simple_return()
        retval.start = self.input.LT(1)

        root_0 = None

        name35 = None

        function36 = None



        try:
            try:

                alt14 = 2
                LA14_0 = self.input.LA(1)

                if (LA14_0 == NAME) :
                    LA14_1 = self.input.LA(2)

                    if ((WS <= LA14_1 <= HAS)) :
                        alt14 = 1
                    elif (LA14_1 == LPAREN) :
                        alt14 = 2
                    else:
                        nvae = NoViableAltException("", 14, 1, self.input)

                        raise nvae

                else:
                    nvae = NoViableAltException("", 14, 0, self.input)

                    raise nvae

                if alt14 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_name_in_simple586)
                    name35 = self.name()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, name35.tree)


                elif alt14 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_function_in_simple592)
                    function36 = self.function()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, function36.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
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

        NAME37 = None

        NAME37_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                NAME37=self.match(self.input, NAME, self.FOLLOW_NAME_in_name605)

                NAME37_tree = self._adaptor.createWithPayload(NAME37)
                self._adaptor.addChild(root_0, NAME37_tree)




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class function_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def function(self, ):

        retval = self.function_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LPAREN39 = None
        RPAREN41 = None
        name38 = None

        arglist40 = None


        LPAREN39_tree = None
        RPAREN41_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_arglist = RewriteRuleSubtreeStream(self._adaptor, "rule arglist")
        stream_name = RewriteRuleSubtreeStream(self._adaptor, "rule name")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_name_in_function618)
                name38 = self.name()

                self._state.following.pop()
                stream_name.add(name38.tree)
                LPAREN39=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_function620)
                stream_LPAREN.add(LPAREN39)
                self._state.following.append(self.FOLLOW_arglist_in_function622)
                arglist40 = self.arglist()

                self._state.following.pop()
                stream_arglist.add(arglist40.tree)
                RPAREN41=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_function624)
                stream_RPAREN.add(RPAREN41)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(FUNCTION, "FUNCTION"), root_1)

                self._adaptor.addChild(root_1, stream_name.nextTree())

                root_2 = self._adaptor.nil()
                root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(ARGS, "ARGS"), root_2)

                self._adaptor.addChild(root_2, stream_arglist.nextTree())

                self._adaptor.addChild(root_1, root_2)

                self._adaptor.addChild(root_0, root_1)



                retval.tree = root_0



                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class arglist_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def arglist(self, ):

        retval = self.arglist_return()
        retval.start = self.input.LT(1)

        root_0 = None

        arg42 = None

        sep43 = None

        arg44 = None



        try:
            try:

                alt16 = 2
                LA16_0 = self.input.LA(1)

                if (LA16_0 == LPAREN or (FLOAT <= LA16_0 <= TEXT) or (47 <= LA16_0 <= 48)) :
                    alt16 = 1
                elif (LA16_0 == RPAREN) :
                    alt16 = 2
                else:
                    nvae = NoViableAltException("", 16, 0, self.input)

                    raise nvae

                if alt16 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_arg_in_arglist651)
                    arg42 = self.arg()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, arg42.tree)

                    while True:
                        alt15 = 2
                        LA15_0 = self.input.LA(1)

                        if (LA15_0 == WS or LA15_0 == 49) :
                            alt15 = 1


                        if alt15 == 1:

                            pass
                            self._state.following.append(self.FOLLOW_sep_in_arglist654)
                            sep43 = self.sep()

                            self._state.following.pop()
                            self._adaptor.addChild(root_0, sep43.tree)
                            self._state.following.append(self.FOLLOW_arg_in_arglist656)
                            arg44 = self.arg()

                            self._state.following.pop()
                            self._adaptor.addChild(root_0, arg44.tree)


                        else:
                            break




                elif alt16 == 2:

                    pass
                    root_0 = self._adaptor.nil()


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class arg_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def arg(self, ):

        retval = self.arg_return()
        retval.start = self.input.LT(1)

        root_0 = None

        atom45 = None

        function46 = None



        try:
            try:

                alt17 = 2
                LA17_0 = self.input.LA(1)

                if (LA17_0 == LPAREN or (FLOAT <= LA17_0 <= INT) or (PHRASE <= LA17_0 <= TEXT) or (47 <= LA17_0 <= 48)) :
                    alt17 = 1
                elif (LA17_0 == NAME) :
                    LA17_2 = self.input.LA(2)

                    if (LA17_2 == WS or LA17_2 == RPAREN or LA17_2 == 49) :
                        alt17 = 1
                    elif (LA17_2 == LPAREN) :
                        alt17 = 2
                    else:
                        nvae = NoViableAltException("", 17, 2, self.input)

                        raise nvae

                else:
                    nvae = NoViableAltException("", 17, 0, self.input)

                    raise nvae

                if alt17 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_atom_in_arg675)
                    atom45 = self.atom()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, atom45.tree)


                elif alt17 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_function_in_arg681)
                    function46 = self.function()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, function46.tree)


                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class andOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def andOp(self, ):

        retval = self.andOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        WS47 = None
        AND48 = None
        WS49 = None

        WS47_tree = None
        AND48_tree = None
        WS49_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                cnt18 = 0
                while True:
                    alt18 = 2
                    LA18_0 = self.input.LA(1)

                    if (LA18_0 == WS) :
                        alt18 = 1


                    if alt18 == 1:

                        pass
                        WS47=self.match(self.input, WS, self.FOLLOW_WS_in_andOp694)

                        WS47_tree = self._adaptor.createWithPayload(WS47)
                        self._adaptor.addChild(root_0, WS47_tree)



                    else:
                        if cnt18 >= 1:
                            break

                        eee = EarlyExitException(18, self.input)
                        raise eee

                    cnt18 += 1



                alt20 = 2
                LA20_0 = self.input.LA(1)

                if (LA20_0 == AND) :
                    alt20 = 1
                if alt20 == 1:

                    pass
                    AND48=self.match(self.input, AND, self.FOLLOW_AND_in_andOp698)

                    AND48_tree = self._adaptor.createWithPayload(AND48)
                    self._adaptor.addChild(root_0, AND48_tree)


                    cnt19 = 0
                    while True:
                        alt19 = 2
                        LA19_0 = self.input.LA(1)

                        if (LA19_0 == WS) :
                            alt19 = 1


                        if alt19 == 1:

                            pass
                            WS49=self.match(self.input, WS, self.FOLLOW_WS_in_andOp700)

                            WS49_tree = self._adaptor.createWithPayload(WS49)
                            self._adaptor.addChild(root_0, WS49_tree)



                        else:
                            if cnt19 >= 1:
                                break

                            eee = EarlyExitException(19, self.input)
                            raise eee

                        cnt19 += 1








                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class orOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def orOp(self, ):

        retval = self.orOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        WS50 = None
        OR51 = None
        WS52 = None

        WS50_tree = None
        OR51_tree = None
        WS52_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                cnt21 = 0
                while True:
                    alt21 = 2
                    LA21_0 = self.input.LA(1)

                    if (LA21_0 == WS) :
                        alt21 = 1


                    if alt21 == 1:

                        pass
                        WS50=self.match(self.input, WS, self.FOLLOW_WS_in_orOp716)

                        WS50_tree = self._adaptor.createWithPayload(WS50)
                        self._adaptor.addChild(root_0, WS50_tree)



                    else:
                        if cnt21 >= 1:
                            break

                        eee = EarlyExitException(21, self.input)
                        raise eee

                    cnt21 += 1


                OR51=self.match(self.input, OR, self.FOLLOW_OR_in_orOp719)

                OR51_tree = self._adaptor.createWithPayload(OR51)
                self._adaptor.addChild(root_0, OR51_tree)


                cnt22 = 0
                while True:
                    alt22 = 2
                    LA22_0 = self.input.LA(1)

                    if (LA22_0 == WS) :
                        alt22 = 1


                    if alt22 == 1:

                        pass
                        WS52=self.match(self.input, WS, self.FOLLOW_WS_in_orOp721)

                        WS52_tree = self._adaptor.createWithPayload(WS52)
                        self._adaptor.addChild(root_0, WS52_tree)



                    else:
                        if cnt22 >= 1:
                            break

                        eee = EarlyExitException(22, self.input)
                        raise eee

                    cnt22 += 1





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class notOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def notOp(self, ):

        retval = self.notOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        char_literal53 = None
        NOT54 = None
        WS55 = None

        char_literal53_tree = None
        NOT54_tree = None
        WS55_tree = None

        try:
            try:

                alt24 = 2
                LA24_0 = self.input.LA(1)

                if (LA24_0 == NEG) :
                    alt24 = 1
                elif (LA24_0 == NOT) :
                    alt24 = 2
                else:
                    nvae = NoViableAltException("", 24, 0, self.input)

                    raise nvae

                if alt24 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    char_literal53=self.match(self.input, NEG, self.FOLLOW_NEG_in_notOp735)

                    char_literal53_tree = self._adaptor.createWithPayload(char_literal53)
                    self._adaptor.addChild(root_0, char_literal53_tree)



                elif alt24 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    NOT54=self.match(self.input, NOT, self.FOLLOW_NOT_in_notOp741)

                    NOT54_tree = self._adaptor.createWithPayload(NOT54)
                    self._adaptor.addChild(root_0, NOT54_tree)


                    cnt23 = 0
                    while True:
                        alt23 = 2
                        LA23_0 = self.input.LA(1)

                        if (LA23_0 == WS) :
                            alt23 = 1


                        if alt23 == 1:

                            pass
                            WS55=self.match(self.input, WS, self.FOLLOW_WS_in_notOp743)

                            WS55_tree = self._adaptor.createWithPayload(WS55)
                            self._adaptor.addChild(root_0, WS55_tree)



                        else:
                            if cnt23 >= 1:
                                break

                            eee = EarlyExitException(23, self.input)
                            raise eee

                        cnt23 += 1




                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval



    class sep_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def sep(self, ):

        retval = self.sep_return()
        retval.start = self.input.LT(1)

        root_0 = None

        WS56 = None
        char_literal57 = None
        WS58 = None

        WS56_tree = None
        char_literal57_tree = None
        WS58_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                while True:
                    alt25 = 2
                    LA25_0 = self.input.LA(1)

                    if (LA25_0 == WS) :
                        alt25 = 1


                    if alt25 == 1:

                        pass
                        WS56=self.match(self.input, WS, self.FOLLOW_WS_in_sep757)

                        WS56_tree = self._adaptor.createWithPayload(WS56)
                        self._adaptor.addChild(root_0, WS56_tree)



                    else:
                        break


                char_literal57=self.match(self.input, 49, self.FOLLOW_49_in_sep760)

                char_literal57_tree = self._adaptor.createWithPayload(char_literal57)
                self._adaptor.addChild(root_0, char_literal57_tree)


                while True:
                    alt26 = 2
                    LA26_0 = self.input.LA(1)

                    if (LA26_0 == WS) :
                        alt26 = 1


                    if alt26 == 1:

                        pass
                        WS58=self.match(self.input, WS, self.FOLLOW_WS_in_sep762)

                        WS58_tree = self._adaptor.createWithPayload(WS58)
                        self._adaptor.addChild(root_0, WS58_tree)



                    else:
                        break





                retval.stop = self.input.LT(-1)


                retval.tree = self._adaptor.rulePostProcessing(root_0)
                self._adaptor.setTokenBoundaries(retval.tree, retval.start, retval.stop)


            except RecognitionException, re:
                self.reportError(re)
                self.recover(self.input, re)
                retval.tree = self._adaptor.errorNode(self.input, retval.start, self.input.LT(-1), re)
        finally:

            pass

        return retval









    DFA2_eot = DFA.unpack(
        u"\4\uffff"
        )

    DFA2_eof = DFA.unpack(
        u"\2\2\2\uffff"
        )

    DFA2_min = DFA.unpack(
        u"\2\21\2\uffff"
        )

    DFA2_max = DFA.unpack(
        u"\1\32\1\60\2\uffff"
        )

    DFA2_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1"
        )

    DFA2_special = DFA.unpack(
        u"\4\uffff"
        )


    DFA2_transition = [
        DFA.unpack(u"\1\1\10\uffff\1\2"),
        DFA.unpack(u"\1\1\7\uffff\1\3\1\2\6\3\1\uffff\1\3\6\uffff\1\3\5"
        u"\uffff\2\3"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA2 = DFA


    DFA4_eot = DFA.unpack(
        u"\4\uffff"
        )

    DFA4_eof = DFA.unpack(
        u"\2\2\2\uffff"
        )

    DFA4_min = DFA.unpack(
        u"\2\21\2\uffff"
        )

    DFA4_max = DFA.unpack(
        u"\1\32\1\60\2\uffff"
        )

    DFA4_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1"
        )

    DFA4_special = DFA.unpack(
        u"\4\uffff"
        )


    DFA4_transition = [
        DFA.unpack(u"\1\1\10\uffff\1\2"),
        DFA.unpack(u"\1\1\7\uffff\10\2\1\3\1\2\6\uffff\1\2\5\uffff\2\2"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA4 = DFA


    DFA6_eot = DFA.unpack(
        u"\5\uffff"
        )

    DFA6_eof = DFA.unpack(
        u"\1\uffff\1\2\1\uffff\1\2\1\uffff"
        )

    DFA6_min = DFA.unpack(
        u"\1\31\1\21\1\uffff\1\21\1\uffff"
        )

    DFA6_max = DFA.unpack(
        u"\1\60\1\32\1\uffff\1\60\1\uffff"
        )

    DFA6_accept = DFA.unpack(
        u"\2\uffff\1\2\1\uffff\1\1"
        )

    DFA6_special = DFA.unpack(
        u"\5\uffff"
        )


    DFA6_transition = [
        DFA.unpack(u"\1\2\1\uffff\2\2\1\1\2\2\17\uffff\2\2"),
        DFA.unpack(u"\1\3\10\4\1\2"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\3\7\4\12\2\6\uffff\1\2\5\uffff\2\2"),
        DFA.unpack(u"")
    ]



    DFA6 = DFA


    FOLLOW_expression_in_query122 = frozenset([])
    FOLLOW_EOF_in_query124 = frozenset([1])
    FOLLOW_WS_in_expression142 = frozenset([17, 25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_factor_in_expression145 = frozenset([1, 17])
    FOLLOW_andOp_in_expression148 = frozenset([25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_factor_in_expression150 = frozenset([1, 17])
    FOLLOW_WS_in_expression154 = frozenset([1, 17])
    FOLLOW_term_in_factor181 = frozenset([1, 17])
    FOLLOW_orOp_in_factor184 = frozenset([25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_term_in_factor186 = frozenset([1, 17])
    FOLLOW_notOp_in_term215 = frozenset([25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_primitive_in_term217 = frozenset([1])
    FOLLOW_primitive_in_term231 = frozenset([1])
    FOLLOW_restrict_in_primitive250 = frozenset([1])
    FOLLOW_atom_in_primitive256 = frozenset([1])
    FOLLOW_simple_in_restrict283 = frozenset([17, 18, 19, 20, 21, 22, 23, 24])
    FOLLOW_comparator_in_restrict285 = frozenset([25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_atom_in_restrict287 = frozenset([1])
    FOLLOW_WS_in_comparator314 = frozenset([17, 18, 19, 20, 21, 22, 23, 24])
    FOLLOW_LE_in_comparator320 = frozenset([1, 17])
    FOLLOW_LT_in_comparator326 = frozenset([1, 17])
    FOLLOW_GE_in_comparator332 = frozenset([1, 17])
    FOLLOW_GT_in_comparator338 = frozenset([1, 17])
    FOLLOW_NE_in_comparator344 = frozenset([1, 17])
    FOLLOW_EQ_in_comparator350 = frozenset([1, 17])
    FOLLOW_HAS_in_comparator356 = frozenset([1, 17])
    FOLLOW_WS_in_comparator359 = frozenset([1, 17])
    FOLLOW_value_in_atom378 = frozenset([1])
    FOLLOW_LPAREN_in_atom384 = frozenset([17, 25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_expression_in_atom386 = frozenset([26])
    FOLLOW_RPAREN_in_atom388 = frozenset([1])
    FOLLOW_text_value_in_value405 = frozenset([1])
    FOLLOW_numeric_value_in_value411 = frozenset([1])
    FOLLOW_set_in_numeric_value0 = frozenset([1])
    FOLLOW_literal_text_in_text_value453 = frozenset([1])
    FOLLOW_rewritable_text_in_text_value459 = frozenset([1])
    FOLLOW_text_in_text_value465 = frozenset([1])
    FOLLOW_47_in_literal_text478 = frozenset([29, 30, 31, 47, 48])
    FOLLOW_text_in_literal_text480 = frozenset([1])
    FOLLOW_48_in_rewritable_text500 = frozenset([29, 30, 31, 47, 48])
    FOLLOW_text_in_rewritable_text502 = frozenset([1])
    FOLLOW_NAME_in_text524 = frozenset([1])
    FOLLOW_PHRASE_in_text543 = frozenset([1])
    FOLLOW_TEXT_in_text562 = frozenset([1])
    FOLLOW_name_in_simple586 = frozenset([1])
    FOLLOW_function_in_simple592 = frozenset([1])
    FOLLOW_NAME_in_name605 = frozenset([1])
    FOLLOW_name_in_function618 = frozenset([25])
    FOLLOW_LPAREN_in_function620 = frozenset([25, 26, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_arglist_in_function622 = frozenset([26])
    FOLLOW_RPAREN_in_function624 = frozenset([1])
    FOLLOW_arg_in_arglist651 = frozenset([1, 17, 49])
    FOLLOW_sep_in_arglist654 = frozenset([25, 27, 28, 29, 30, 31, 34, 41, 47, 48])
    FOLLOW_arg_in_arglist656 = frozenset([1, 17, 49])
    FOLLOW_atom_in_arg675 = frozenset([1])
    FOLLOW_function_in_arg681 = frozenset([1])
    FOLLOW_WS_in_andOp694 = frozenset([1, 17, 32])
    FOLLOW_AND_in_andOp698 = frozenset([17])
    FOLLOW_WS_in_andOp700 = frozenset([1, 17])
    FOLLOW_WS_in_orOp716 = frozenset([17, 33])
    FOLLOW_OR_in_orOp719 = frozenset([17])
    FOLLOW_WS_in_orOp721 = frozenset([1, 17])
    FOLLOW_NEG_in_notOp735 = frozenset([1])
    FOLLOW_NOT_in_notOp741 = frozenset([17])
    FOLLOW_WS_in_notOp743 = frozenset([1, 17])
    FOLLOW_WS_in_sep757 = frozenset([17, 49])
    FOLLOW_49_in_sep760 = frozenset([1, 17])
    FOLLOW_WS_in_sep762 = frozenset([1, 17])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import ParserMain
    main = ParserMain("QueryLexer", QueryParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
