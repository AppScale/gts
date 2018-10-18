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
GEO_POINT_FN=29
FIX=30
ESC=34
FUZZY=8
OCTAL_ESC=36
NOT=27
AND=25
DISTANCE_FN=28
EOF=-1
ESCAPED_CHAR=40
LPAREN=23
HAS=22
RPAREN=24
QUOTE=33
CHAR_SEQ=37
START_CHAR=41
ARGS=4
DIGIT=38
EQ=21
NE=20
T__43=43
LESSTHAN=17
GE=18
T__44=44
T__45=45
CONJUNCTION=5
UNICODE_ESC=35
HEX_DIGIT=42
LITERAL=10
VALUE=14
TEXT=32
REWRITE=31
SEQUENCE=13
DISJUNCTION=6
WS=15
NEGATION=11
OR=26
GT=19
GLOBAL=9
LE=16
MID_CHAR=39
STRING=12


tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "ARGS", "CONJUNCTION", "DISJUNCTION", "FUNCTION", "FUZZY", "GLOBAL",
    "LITERAL", "NEGATION", "STRING", "SEQUENCE", "VALUE", "WS", "LE", "LESSTHAN",
    "GE", "GT", "NE", "EQ", "HAS", "LPAREN", "RPAREN", "AND", "OR", "NOT",
    "DISTANCE_FN", "GEO_POINT_FN", "FIX", "REWRITE", "TEXT", "QUOTE", "ESC",
    "UNICODE_ESC", "OCTAL_ESC", "CHAR_SEQ", "DIGIT", "MID_CHAR", "ESCAPED_CHAR",
    "START_CHAR", "HEX_DIGIT", "'-'", "','", "'\\\\'"
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


        self.dfa3 = self.DFA3(
            self, 3,
            eot = self.DFA3_eot,
            eof = self.DFA3_eof,
            min = self.DFA3_min,
            max = self.DFA3_max,
            accept = self.DFA3_accept,
            special = self.DFA3_special,
            transition = self.DFA3_transition
            )

        self.dfa5 = self.DFA5(
            self, 5,
            eot = self.DFA5_eot,
            eof = self.DFA5_eof,
            min = self.DFA5_min,
            max = self.DFA5_max,
            accept = self.DFA5_accept,
            special = self.DFA5_special,
            transition = self.DFA5_transition
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

        self.dfa8 = self.DFA8(
            self, 8,
            eot = self.DFA8_eot,
            eof = self.DFA8_eof,
            min = self.DFA8_min,
            max = self.DFA8_max,
            accept = self.DFA8_accept,
            special = self.DFA8_special,
            transition = self.DFA8_transition
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

        WS1 = None
        WS3 = None
        EOF4 = None
        expression2 = None


        WS1_tree = None
        WS3_tree = None
        EOF4_tree = None
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_EOF = RewriteRuleTokenStream(self._adaptor, "token EOF")
        stream_expression = RewriteRuleSubtreeStream(self._adaptor, "rule expression")
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
                        WS1=self.match(self.input, WS, self.FOLLOW_WS_in_query112)
                        stream_WS.add(WS1)


                    else:
                        break


                self._state.following.append(self.FOLLOW_expression_in_query115)
                expression2 = self.expression()

                self._state.following.pop()
                stream_expression.add(expression2.tree)

                while True:
                    alt2 = 2
                    LA2_0 = self.input.LA(1)

                    if (LA2_0 == WS) :
                        alt2 = 1


                    if alt2 == 1:

                        pass
                        WS3=self.match(self.input, WS, self.FOLLOW_WS_in_query117)
                        stream_WS.add(WS3)


                    else:
                        break


                EOF4=self.match(self.input, EOF, self.FOLLOW_EOF_in_query120)
                stream_EOF.add(EOF4)








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



    class expression_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def expression(self, ):

        retval = self.expression_return()
        retval.start = self.input.LT(1)

        root_0 = None

        sequence5 = None

        andOp6 = None

        sequence7 = None


        stream_sequence = RewriteRuleSubtreeStream(self._adaptor, "rule sequence")
        stream_andOp = RewriteRuleSubtreeStream(self._adaptor, "rule andOp")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_sequence_in_expression139)
                sequence5 = self.sequence()

                self._state.following.pop()
                stream_sequence.add(sequence5.tree)

                while True:
                    alt3 = 2
                    alt3 = self.dfa3.predict(self.input)
                    if alt3 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_andOp_in_expression142)
                        andOp6 = self.andOp()

                        self._state.following.pop()
                        stream_andOp.add(andOp6.tree)
                        self._state.following.append(self.FOLLOW_sequence_in_expression144)
                        sequence7 = self.sequence()

                        self._state.following.pop()
                        stream_sequence.add(sequence7.tree)


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


                if not (stream_sequence.hasNext()):
                    raise RewriteEarlyExitException()

                while stream_sequence.hasNext():
                    self._adaptor.addChild(root_1, stream_sequence.nextTree())


                stream_sequence.reset()

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



    class sequence_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def sequence(self, ):

        retval = self.sequence_return()
        retval.start = self.input.LT(1)

        root_0 = None

        WS9 = None
        factor8 = None

        factor10 = None


        WS9_tree = None
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_factor = RewriteRuleSubtreeStream(self._adaptor, "rule factor")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_factor_in_sequence170)
                factor8 = self.factor()

                self._state.following.pop()
                stream_factor.add(factor8.tree)

                while True:
                    alt5 = 2
                    alt5 = self.dfa5.predict(self.input)
                    if alt5 == 1:

                        pass

                        cnt4 = 0
                        while True:
                            alt4 = 2
                            LA4_0 = self.input.LA(1)

                            if (LA4_0 == WS) :
                                alt4 = 1


                            if alt4 == 1:

                                pass
                                WS9=self.match(self.input, WS, self.FOLLOW_WS_in_sequence173)
                                stream_WS.add(WS9)


                            else:
                                if cnt4 >= 1:
                                    break

                                eee = EarlyExitException(4, self.input)
                                raise eee

                            cnt4 += 1


                        self._state.following.append(self.FOLLOW_factor_in_sequence176)
                        factor10 = self.factor()

                        self._state.following.pop()
                        stream_factor.add(factor10.tree)


                    else:
                        break










                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(SEQUENCE, "SEQUENCE"), root_1)


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

        term11 = None

        orOp12 = None

        term13 = None


        stream_orOp = RewriteRuleSubtreeStream(self._adaptor, "rule orOp")
        stream_term = RewriteRuleSubtreeStream(self._adaptor, "rule term")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_term_in_factor202)
                term11 = self.term()

                self._state.following.pop()
                stream_term.add(term11.tree)

                while True:
                    alt6 = 2
                    alt6 = self.dfa6.predict(self.input)
                    if alt6 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_orOp_in_factor205)
                        orOp12 = self.orOp()

                        self._state.following.pop()
                        stream_orOp.add(orOp12.tree)
                        self._state.following.append(self.FOLLOW_term_in_factor207)
                        term13 = self.term()

                        self._state.following.pop()
                        stream_term.add(term13.tree)


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

        notOp14 = None

        primitive15 = None

        primitive16 = None


        stream_notOp = RewriteRuleSubtreeStream(self._adaptor, "rule notOp")
        stream_primitive = RewriteRuleSubtreeStream(self._adaptor, "rule primitive")
        try:
            try:

                alt7 = 2
                LA7_0 = self.input.LA(1)

                if (LA7_0 == NOT or LA7_0 == 43) :
                    alt7 = 1
                elif (LA7_0 == LPAREN or (DISTANCE_FN <= LA7_0 <= QUOTE)) :
                    alt7 = 2
                else:
                    nvae = NoViableAltException("", 7, 0, self.input)

                    raise nvae

                if alt7 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_notOp_in_term231)
                    notOp14 = self.notOp()

                    self._state.following.pop()
                    stream_notOp.add(notOp14.tree)
                    self._state.following.append(self.FOLLOW_primitive_in_term233)
                    primitive15 = self.primitive()

                    self._state.following.pop()
                    stream_primitive.add(primitive15.tree)








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


                elif alt7 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_primitive_in_term247)
                    primitive16 = self.primitive()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, primitive16.tree)


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

        restriction17 = None

        composite18 = None

        item19 = None


        stream_item = RewriteRuleSubtreeStream(self._adaptor, "rule item")
        try:
            try:

                alt8 = 3
                alt8 = self.dfa8.predict(self.input)
                if alt8 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_restriction_in_primitive263)
                    restriction17 = self.restriction()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, restriction17.tree)


                elif alt8 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_composite_in_primitive269)
                    composite18 = self.composite()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, composite18.tree)


                elif alt8 == 3:

                    pass
                    self._state.following.append(self.FOLLOW_item_in_primitive275)
                    item19 = self.item()

                    self._state.following.pop()
                    stream_item.add(item19.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(HAS, "HAS"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(GLOBAL, "GLOBAL"))
                    self._adaptor.addChild(root_1, stream_item.nextTree())

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



    class restriction_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def restriction(self, ):

        retval = self.restriction_return()
        retval.start = self.input.LT(1)

        root_0 = None

        comparable20 = None

        comparator21 = None

        arg22 = None


        stream_arg = RewriteRuleSubtreeStream(self._adaptor, "rule arg")
        stream_comparable = RewriteRuleSubtreeStream(self._adaptor, "rule comparable")
        stream_comparator = RewriteRuleSubtreeStream(self._adaptor, "rule comparator")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_comparable_in_restriction301)
                comparable20 = self.comparable()

                self._state.following.pop()
                stream_comparable.add(comparable20.tree)
                self._state.following.append(self.FOLLOW_comparator_in_restriction303)
                comparator21 = self.comparator()

                self._state.following.pop()
                stream_comparator.add(comparator21.tree)
                self._state.following.append(self.FOLLOW_arg_in_restriction305)
                arg22 = self.arg()

                self._state.following.pop()
                stream_arg.add(arg22.tree)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(stream_comparator.nextNode(), root_1)

                self._adaptor.addChild(root_1, stream_comparable.nextTree())
                self._adaptor.addChild(root_1, stream_arg.nextTree())

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
        WS23 = None
        WS24 = None

        x_tree = None
        WS23_tree = None
        WS24_tree = None
        stream_HAS = RewriteRuleTokenStream(self._adaptor, "token HAS")
        stream_LESSTHAN = RewriteRuleTokenStream(self._adaptor, "token LESSTHAN")
        stream_GE = RewriteRuleTokenStream(self._adaptor, "token GE")
        stream_GT = RewriteRuleTokenStream(self._adaptor, "token GT")
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_EQ = RewriteRuleTokenStream(self._adaptor, "token EQ")
        stream_LE = RewriteRuleTokenStream(self._adaptor, "token LE")
        stream_NE = RewriteRuleTokenStream(self._adaptor, "token NE")

        try:
            try:


                pass

                while True:
                    alt9 = 2
                    LA9_0 = self.input.LA(1)

                    if (LA9_0 == WS) :
                        alt9 = 1


                    if alt9 == 1:

                        pass
                        WS23=self.match(self.input, WS, self.FOLLOW_WS_in_comparator329)
                        stream_WS.add(WS23)


                    else:
                        break



                alt10 = 7
                LA10 = self.input.LA(1)
                if LA10 == LE:
                    alt10 = 1
                elif LA10 == LESSTHAN:
                    alt10 = 2
                elif LA10 == GE:
                    alt10 = 3
                elif LA10 == GT:
                    alt10 = 4
                elif LA10 == NE:
                    alt10 = 5
                elif LA10 == EQ:
                    alt10 = 6
                elif LA10 == HAS:
                    alt10 = 7
                else:
                    nvae = NoViableAltException("", 10, 0, self.input)

                    raise nvae

                if alt10 == 1:

                    pass
                    x=self.match(self.input, LE, self.FOLLOW_LE_in_comparator335)
                    stream_LE.add(x)


                elif alt10 == 2:

                    pass
                    x=self.match(self.input, LESSTHAN, self.FOLLOW_LESSTHAN_in_comparator341)
                    stream_LESSTHAN.add(x)


                elif alt10 == 3:

                    pass
                    x=self.match(self.input, GE, self.FOLLOW_GE_in_comparator347)
                    stream_GE.add(x)


                elif alt10 == 4:

                    pass
                    x=self.match(self.input, GT, self.FOLLOW_GT_in_comparator353)
                    stream_GT.add(x)


                elif alt10 == 5:

                    pass
                    x=self.match(self.input, NE, self.FOLLOW_NE_in_comparator359)
                    stream_NE.add(x)


                elif alt10 == 6:

                    pass
                    x=self.match(self.input, EQ, self.FOLLOW_EQ_in_comparator365)
                    stream_EQ.add(x)


                elif alt10 == 7:

                    pass
                    x=self.match(self.input, HAS, self.FOLLOW_HAS_in_comparator371)
                    stream_HAS.add(x)




                while True:
                    alt11 = 2
                    LA11_0 = self.input.LA(1)

                    if (LA11_0 == WS) :
                        alt11 = 1


                    if alt11 == 1:

                        pass
                        WS24=self.match(self.input, WS, self.FOLLOW_WS_in_comparator374)
                        stream_WS.add(WS24)


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



    class comparable_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def comparable(self, ):

        retval = self.comparable_return()
        retval.start = self.input.LT(1)

        root_0 = None

        item25 = None

        function26 = None



        try:
            try:

                alt12 = 2
                LA12 = self.input.LA(1)
                if LA12 == FIX or LA12 == REWRITE or LA12 == TEXT or LA12 == QUOTE:
                    alt12 = 1
                elif LA12 == DISTANCE_FN:
                    LA12_2 = self.input.LA(2)

                    if ((WS <= LA12_2 <= HAS)) :
                        alt12 = 1
                    elif (LA12_2 == LPAREN) :
                        alt12 = 2
                    else:
                        nvae = NoViableAltException("", 12, 2, self.input)

                        raise nvae

                elif LA12 == GEO_POINT_FN:
                    LA12_3 = self.input.LA(2)

                    if ((WS <= LA12_3 <= HAS)) :
                        alt12 = 1
                    elif (LA12_3 == LPAREN) :
                        alt12 = 2
                    else:
                        nvae = NoViableAltException("", 12, 3, self.input)

                        raise nvae

                else:
                    nvae = NoViableAltException("", 12, 0, self.input)

                    raise nvae

                if alt12 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_item_in_comparable396)
                    item25 = self.item()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, item25.tree)


                elif alt12 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_function_in_comparable402)
                    function26 = self.function()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, function26.tree)


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

        LPAREN28 = None
        RPAREN30 = None
        fnname27 = None

        arglist29 = None


        LPAREN28_tree = None
        RPAREN30_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_arglist = RewriteRuleSubtreeStream(self._adaptor, "rule arglist")
        stream_fnname = RewriteRuleSubtreeStream(self._adaptor, "rule fnname")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_fnname_in_function417)
                fnname27 = self.fnname()

                self._state.following.pop()
                stream_fnname.add(fnname27.tree)
                LPAREN28=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_function419)
                stream_LPAREN.add(LPAREN28)
                self._state.following.append(self.FOLLOW_arglist_in_function421)
                arglist29 = self.arglist()

                self._state.following.pop()
                stream_arglist.add(arglist29.tree)
                RPAREN30=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_function423)
                stream_RPAREN.add(RPAREN30)








                retval.tree = root_0

                if retval is not None:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                else:
                    stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                root_0 = self._adaptor.nil()


                root_1 = self._adaptor.nil()
                root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(FUNCTION, "FUNCTION"), root_1)

                self._adaptor.addChild(root_1, stream_fnname.nextTree())

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

        arg31 = None

        sep32 = None

        arg33 = None


        stream_arg = RewriteRuleSubtreeStream(self._adaptor, "rule arg")
        stream_sep = RewriteRuleSubtreeStream(self._adaptor, "rule sep")
        try:
            try:

                alt14 = 2
                LA14_0 = self.input.LA(1)

                if (LA14_0 == LPAREN or (DISTANCE_FN <= LA14_0 <= QUOTE)) :
                    alt14 = 1
                elif (LA14_0 == RPAREN) :
                    alt14 = 2
                else:
                    nvae = NoViableAltException("", 14, 0, self.input)

                    raise nvae

                if alt14 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_arg_in_arglist452)
                    arg31 = self.arg()

                    self._state.following.pop()
                    stream_arg.add(arg31.tree)

                    while True:
                        alt13 = 2
                        LA13_0 = self.input.LA(1)

                        if (LA13_0 == WS or LA13_0 == 44) :
                            alt13 = 1


                        if alt13 == 1:

                            pass
                            self._state.following.append(self.FOLLOW_sep_in_arglist455)
                            sep32 = self.sep()

                            self._state.following.pop()
                            stream_sep.add(sep32.tree)
                            self._state.following.append(self.FOLLOW_arg_in_arglist457)
                            arg33 = self.arg()

                            self._state.following.pop()
                            stream_arg.add(arg33.tree)


                        else:
                            break










                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    while stream_arg.hasNext():
                        self._adaptor.addChild(root_0, stream_arg.nextTree())


                    stream_arg.reset();



                    retval.tree = root_0


                elif alt14 == 2:

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

        item34 = None

        composite35 = None

        function36 = None



        try:
            try:

                alt15 = 3
                LA15 = self.input.LA(1)
                if LA15 == FIX or LA15 == REWRITE or LA15 == TEXT or LA15 == QUOTE:
                    alt15 = 1
                elif LA15 == DISTANCE_FN:
                    LA15_2 = self.input.LA(2)

                    if (LA15_2 == EOF or LA15_2 == WS or LA15_2 == RPAREN or LA15_2 == 44) :
                        alt15 = 1
                    elif (LA15_2 == LPAREN) :
                        alt15 = 3
                    else:
                        nvae = NoViableAltException("", 15, 2, self.input)

                        raise nvae

                elif LA15 == GEO_POINT_FN:
                    LA15_3 = self.input.LA(2)

                    if (LA15_3 == EOF or LA15_3 == WS or LA15_3 == RPAREN or LA15_3 == 44) :
                        alt15 = 1
                    elif (LA15_3 == LPAREN) :
                        alt15 = 3
                    else:
                        nvae = NoViableAltException("", 15, 3, self.input)

                        raise nvae

                elif LA15 == LPAREN:
                    alt15 = 2
                else:
                    nvae = NoViableAltException("", 15, 0, self.input)

                    raise nvae

                if alt15 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_item_in_arg482)
                    item34 = self.item()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, item34.tree)


                elif alt15 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_composite_in_arg488)
                    composite35 = self.composite()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, composite35.tree)


                elif alt15 == 3:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_function_in_arg494)
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



    class andOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def andOp(self, ):

        retval = self.andOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        WS37 = None
        AND38 = None
        WS39 = None

        WS37_tree = None
        AND38_tree = None
        WS39_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                cnt16 = 0
                while True:
                    alt16 = 2
                    LA16_0 = self.input.LA(1)

                    if (LA16_0 == WS) :
                        alt16 = 1


                    if alt16 == 1:

                        pass
                        WS37=self.match(self.input, WS, self.FOLLOW_WS_in_andOp508)

                        WS37_tree = self._adaptor.createWithPayload(WS37)
                        self._adaptor.addChild(root_0, WS37_tree)



                    else:
                        if cnt16 >= 1:
                            break

                        eee = EarlyExitException(16, self.input)
                        raise eee

                    cnt16 += 1


                AND38=self.match(self.input, AND, self.FOLLOW_AND_in_andOp511)

                AND38_tree = self._adaptor.createWithPayload(AND38)
                self._adaptor.addChild(root_0, AND38_tree)


                cnt17 = 0
                while True:
                    alt17 = 2
                    LA17_0 = self.input.LA(1)

                    if (LA17_0 == WS) :
                        alt17 = 1


                    if alt17 == 1:

                        pass
                        WS39=self.match(self.input, WS, self.FOLLOW_WS_in_andOp513)

                        WS39_tree = self._adaptor.createWithPayload(WS39)
                        self._adaptor.addChild(root_0, WS39_tree)



                    else:
                        if cnt17 >= 1:
                            break

                        eee = EarlyExitException(17, self.input)
                        raise eee

                    cnt17 += 1





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

        WS40 = None
        OR41 = None
        WS42 = None

        WS40_tree = None
        OR41_tree = None
        WS42_tree = None

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
                        WS40=self.match(self.input, WS, self.FOLLOW_WS_in_orOp528)

                        WS40_tree = self._adaptor.createWithPayload(WS40)
                        self._adaptor.addChild(root_0, WS40_tree)



                    else:
                        if cnt18 >= 1:
                            break

                        eee = EarlyExitException(18, self.input)
                        raise eee

                    cnt18 += 1


                OR41=self.match(self.input, OR, self.FOLLOW_OR_in_orOp531)

                OR41_tree = self._adaptor.createWithPayload(OR41)
                self._adaptor.addChild(root_0, OR41_tree)


                cnt19 = 0
                while True:
                    alt19 = 2
                    LA19_0 = self.input.LA(1)

                    if (LA19_0 == WS) :
                        alt19 = 1


                    if alt19 == 1:

                        pass
                        WS42=self.match(self.input, WS, self.FOLLOW_WS_in_orOp533)

                        WS42_tree = self._adaptor.createWithPayload(WS42)
                        self._adaptor.addChild(root_0, WS42_tree)



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



    class notOp_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def notOp(self, ):

        retval = self.notOp_return()
        retval.start = self.input.LT(1)

        root_0 = None

        char_literal43 = None
        NOT44 = None
        WS45 = None

        char_literal43_tree = None
        NOT44_tree = None
        WS45_tree = None

        try:
            try:

                alt21 = 2
                LA21_0 = self.input.LA(1)

                if (LA21_0 == 43) :
                    alt21 = 1
                elif (LA21_0 == NOT) :
                    alt21 = 2
                else:
                    nvae = NoViableAltException("", 21, 0, self.input)

                    raise nvae

                if alt21 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    char_literal43=self.match(self.input, 43, self.FOLLOW_43_in_notOp548)

                    char_literal43_tree = self._adaptor.createWithPayload(char_literal43)
                    self._adaptor.addChild(root_0, char_literal43_tree)



                elif alt21 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    NOT44=self.match(self.input, NOT, self.FOLLOW_NOT_in_notOp554)

                    NOT44_tree = self._adaptor.createWithPayload(NOT44)
                    self._adaptor.addChild(root_0, NOT44_tree)


                    cnt20 = 0
                    while True:
                        alt20 = 2
                        LA20_0 = self.input.LA(1)

                        if (LA20_0 == WS) :
                            alt20 = 1


                        if alt20 == 1:

                            pass
                            WS45=self.match(self.input, WS, self.FOLLOW_WS_in_notOp556)

                            WS45_tree = self._adaptor.createWithPayload(WS45)
                            self._adaptor.addChild(root_0, WS45_tree)



                        else:
                            if cnt20 >= 1:
                                break

                            eee = EarlyExitException(20, self.input)
                            raise eee

                        cnt20 += 1




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

        WS46 = None
        char_literal47 = None
        WS48 = None

        WS46_tree = None
        char_literal47_tree = None
        WS48_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                while True:
                    alt22 = 2
                    LA22_0 = self.input.LA(1)

                    if (LA22_0 == WS) :
                        alt22 = 1


                    if alt22 == 1:

                        pass
                        WS46=self.match(self.input, WS, self.FOLLOW_WS_in_sep571)

                        WS46_tree = self._adaptor.createWithPayload(WS46)
                        self._adaptor.addChild(root_0, WS46_tree)



                    else:
                        break


                char_literal47=self.match(self.input, 44, self.FOLLOW_44_in_sep574)

                char_literal47_tree = self._adaptor.createWithPayload(char_literal47)
                self._adaptor.addChild(root_0, char_literal47_tree)


                while True:
                    alt23 = 2
                    LA23_0 = self.input.LA(1)

                    if (LA23_0 == WS) :
                        alt23 = 1


                    if alt23 == 1:

                        pass
                        WS48=self.match(self.input, WS, self.FOLLOW_WS_in_sep576)

                        WS48_tree = self._adaptor.createWithPayload(WS48)
                        self._adaptor.addChild(root_0, WS48_tree)



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



    class fnname_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def fnname(self, ):

        retval = self.fnname_return()
        retval.start = self.input.LT(1)

        root_0 = None

        set49 = None

        set49_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set49 = self.input.LT(1)
                if (DISTANCE_FN <= self.input.LA(1) <= GEO_POINT_FN):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set49))
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



    class composite_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def composite(self, ):

        retval = self.composite_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LPAREN50 = None
        WS51 = None
        WS53 = None
        RPAREN54 = None
        expression52 = None


        LPAREN50_tree = None
        WS51_tree = None
        WS53_tree = None
        RPAREN54_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_expression = RewriteRuleSubtreeStream(self._adaptor, "rule expression")
        try:
            try:


                pass
                LPAREN50=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_composite612)
                stream_LPAREN.add(LPAREN50)

                while True:
                    alt24 = 2
                    LA24_0 = self.input.LA(1)

                    if (LA24_0 == WS) :
                        alt24 = 1


                    if alt24 == 1:

                        pass
                        WS51=self.match(self.input, WS, self.FOLLOW_WS_in_composite614)
                        stream_WS.add(WS51)


                    else:
                        break


                self._state.following.append(self.FOLLOW_expression_in_composite617)
                expression52 = self.expression()

                self._state.following.pop()
                stream_expression.add(expression52.tree)

                while True:
                    alt25 = 2
                    LA25_0 = self.input.LA(1)

                    if (LA25_0 == WS) :
                        alt25 = 1


                    if alt25 == 1:

                        pass
                        WS53=self.match(self.input, WS, self.FOLLOW_WS_in_composite619)
                        stream_WS.add(WS53)


                    else:
                        break


                RPAREN54=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_composite622)
                stream_RPAREN.add(RPAREN54)








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



    class item_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def item(self, ):

        retval = self.item_return()
        retval.start = self.input.LT(1)

        root_0 = None

        FIX55 = None
        REWRITE57 = None
        value56 = None

        value58 = None

        value59 = None


        FIX55_tree = None
        REWRITE57_tree = None
        stream_FIX = RewriteRuleTokenStream(self._adaptor, "token FIX")
        stream_REWRITE = RewriteRuleTokenStream(self._adaptor, "token REWRITE")
        stream_value = RewriteRuleSubtreeStream(self._adaptor, "rule value")
        try:
            try:

                alt26 = 3
                LA26 = self.input.LA(1)
                if LA26 == FIX:
                    alt26 = 1
                elif LA26 == REWRITE:
                    alt26 = 2
                elif LA26 == DISTANCE_FN or LA26 == GEO_POINT_FN or LA26 == TEXT or LA26 == QUOTE:
                    alt26 = 3
                else:
                    nvae = NoViableAltException("", 26, 0, self.input)

                    raise nvae

                if alt26 == 1:

                    pass
                    FIX55=self.match(self.input, FIX, self.FOLLOW_FIX_in_item642)
                    stream_FIX.add(FIX55)
                    self._state.following.append(self.FOLLOW_value_in_item644)
                    value56 = self.value()

                    self._state.following.pop()
                    stream_value.add(value56.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(LITERAL, "LITERAL"), root_1)

                    self._adaptor.addChild(root_1, stream_value.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt26 == 2:

                    pass
                    REWRITE57=self.match(self.input, REWRITE, self.FOLLOW_REWRITE_in_item658)
                    stream_REWRITE.add(REWRITE57)
                    self._state.following.append(self.FOLLOW_value_in_item660)
                    value58 = self.value()

                    self._state.following.pop()
                    stream_value.add(value58.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(FUZZY, "FUZZY"), root_1)

                    self._adaptor.addChild(root_1, stream_value.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt26 == 3:

                    pass
                    self._state.following.append(self.FOLLOW_value_in_item674)
                    value59 = self.value()

                    self._state.following.pop()
                    stream_value.add(value59.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, stream_value.nextTree())



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

        text60 = None

        phrase61 = None


        stream_text = RewriteRuleSubtreeStream(self._adaptor, "rule text")
        stream_phrase = RewriteRuleSubtreeStream(self._adaptor, "rule phrase")
        try:
            try:

                alt27 = 2
                LA27_0 = self.input.LA(1)

                if ((DISTANCE_FN <= LA27_0 <= GEO_POINT_FN) or LA27_0 == TEXT) :
                    alt27 = 1
                elif (LA27_0 == QUOTE) :
                    alt27 = 2
                else:
                    nvae = NoViableAltException("", 27, 0, self.input)

                    raise nvae

                if alt27 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_text_in_value692)
                    text60 = self.text()

                    self._state.following.pop()
                    stream_text.add(text60.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(TEXT, "TEXT"))
                    self._adaptor.addChild(root_1, stream_text.nextTree())

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt27 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_phrase_in_value708)
                    phrase61 = self.phrase()

                    self._state.following.pop()
                    stream_phrase.add(phrase61.tree)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(STRING, "STRING"))
                    self._adaptor.addChild(root_1, stream_phrase.nextTree())

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

        t = None
        TEXT62 = None

        t_tree = None
        TEXT62_tree = None
        stream_GEO_POINT_FN = RewriteRuleTokenStream(self._adaptor, "token GEO_POINT_FN")
        stream_DISTANCE_FN = RewriteRuleTokenStream(self._adaptor, "token DISTANCE_FN")

        try:
            try:

                alt28 = 3
                LA28 = self.input.LA(1)
                if LA28 == TEXT:
                    alt28 = 1
                elif LA28 == DISTANCE_FN:
                    alt28 = 2
                elif LA28 == GEO_POINT_FN:
                    alt28 = 3
                else:
                    nvae = NoViableAltException("", 28, 0, self.input)

                    raise nvae

                if alt28 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    TEXT62=self.match(self.input, TEXT, self.FOLLOW_TEXT_in_text732)

                    TEXT62_tree = self._adaptor.createWithPayload(TEXT62)
                    self._adaptor.addChild(root_0, TEXT62_tree)



                elif alt28 == 2:

                    pass
                    t=self.match(self.input, DISTANCE_FN, self.FOLLOW_DISTANCE_FN_in_text743)
                    stream_DISTANCE_FN.add(t)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, self._adaptor.create(TEXT, t))



                    retval.tree = root_0


                elif alt28 == 3:

                    pass
                    t=self.match(self.input, GEO_POINT_FN, self.FOLLOW_GEO_POINT_FN_in_text756)
                    stream_GEO_POINT_FN.add(t)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()

                    self._adaptor.addChild(root_0, self._adaptor.create(TEXT, t))



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



    class phrase_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def phrase(self, ):

        retval = self.phrase_return()
        retval.start = self.input.LT(1)

        root_0 = None

        QUOTE63 = None
        set64 = None
        QUOTE65 = None

        QUOTE63_tree = None
        set64_tree = None
        QUOTE65_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                QUOTE63=self.match(self.input, QUOTE, self.FOLLOW_QUOTE_in_phrase775)

                QUOTE63_tree = self._adaptor.createWithPayload(QUOTE63)
                self._adaptor.addChild(root_0, QUOTE63_tree)


                while True:
                    alt29 = 2
                    LA29_0 = self.input.LA(1)

                    if ((ARGS <= LA29_0 <= TEXT) or (ESC <= LA29_0 <= 44)) :
                        alt29 = 1


                    if alt29 == 1:

                        pass
                        set64 = self.input.LT(1)
                        if (ARGS <= self.input.LA(1) <= TEXT) or (ESC <= self.input.LA(1) <= 44):
                            self.input.consume()
                            self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set64))
                            self._state.errorRecovery = False

                        else:
                            mse = MismatchedSetException(None, self.input)
                            raise mse




                    else:
                        break


                QUOTE65=self.match(self.input, QUOTE, self.FOLLOW_QUOTE_in_phrase793)

                QUOTE65_tree = self._adaptor.createWithPayload(QUOTE65)
                self._adaptor.addChild(root_0, QUOTE65_tree)




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









    DFA3_eot = DFA.unpack(
        u"\4\uffff"
        )

    DFA3_eof = DFA.unpack(
        u"\2\2\2\uffff"
        )

    DFA3_min = DFA.unpack(
        u"\2\17\2\uffff"
        )

    DFA3_max = DFA.unpack(
        u"\1\30\1\31\2\uffff"
        )

    DFA3_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1"
        )

    DFA3_special = DFA.unpack(
        u"\4\uffff"
        )


    DFA3_transition = [
        DFA.unpack(u"\1\1\10\uffff\1\2"),
        DFA.unpack(u"\1\1\10\uffff\1\2\1\3"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA3 = DFA


    DFA5_eot = DFA.unpack(
        u"\4\uffff"
        )

    DFA5_eof = DFA.unpack(
        u"\2\2\2\uffff"
        )

    DFA5_min = DFA.unpack(
        u"\2\17\2\uffff"
        )

    DFA5_max = DFA.unpack(
        u"\1\30\1\53\2\uffff"
        )

    DFA5_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1"
        )

    DFA5_special = DFA.unpack(
        u"\4\uffff"
        )


    DFA5_transition = [
        DFA.unpack(u"\1\1\10\uffff\1\2"),
        DFA.unpack(u"\1\1\7\uffff\1\3\2\2\1\uffff\7\3\11\uffff\1\3"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA5 = DFA


    DFA6_eot = DFA.unpack(
        u"\4\uffff"
        )

    DFA6_eof = DFA.unpack(
        u"\2\2\2\uffff"
        )

    DFA6_min = DFA.unpack(
        u"\2\17\2\uffff"
        )

    DFA6_max = DFA.unpack(
        u"\1\30\1\53\2\uffff"
        )

    DFA6_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1"
        )

    DFA6_special = DFA.unpack(
        u"\4\uffff"
        )


    DFA6_transition = [
        DFA.unpack(u"\1\1\10\uffff\1\2"),
        DFA.unpack(u"\1\1\7\uffff\3\2\1\3\7\2\11\uffff\1\2"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA6 = DFA


    DFA8_eot = DFA.unpack(
        u"\31\uffff"
        )

    DFA8_eof = DFA.unpack(
        u"\3\uffff\3\21\2\uffff\3\21\1\uffff\3\21\1\uffff\1\21\3\uffff\1"
        u"\21\1\uffff\1\21\1\uffff\1\21"
        )

    DFA8_min = DFA.unpack(
        u"\1\27\2\34\3\17\1\4\1\uffff\3\17\1\4\3\17\1\4\1\17\2\uffff\1\4"
        u"\1\17\1\4\1\17\1\4\1\17"
        )

    DFA8_max = DFA.unpack(
        u"\3\41\3\30\1\54\1\uffff\3\30\1\54\3\30\1\54\1\53\2\uffff\1\54\1"
        u"\30\1\54\1\30\1\54\1\30"
        )

    DFA8_accept = DFA.unpack(
        u"\7\uffff\1\2\11\uffff\1\3\1\1\6\uffff"
        )

    DFA8_special = DFA.unpack(
        u"\31\uffff"
        )


    DFA8_transition = [
        DFA.unpack(u"\1\7\4\uffff\1\4\1\5\1\1\1\2\1\3\1\6"),
        DFA.unpack(u"\1\11\1\12\2\uffff\1\10\1\13"),
        DFA.unpack(u"\1\15\1\16\2\uffff\1\14\1\17"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\1\20\10\22\1\21"),
        DFA.unpack(u"\1\20\10\22\1\21"),
        DFA.unpack(u"\35\23\1\24\13\23"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\35\25\1\26\13\25"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\35\27\1\30\13\27"),
        DFA.unpack(u"\1\20\7\22\13\21\11\uffff\1\21"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\35\23\1\24\13\23"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\35\25\1\26\13\25"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21"),
        DFA.unpack(u"\35\27\1\30\13\27"),
        DFA.unpack(u"\1\20\7\22\1\uffff\1\21")
    ]



    DFA8 = DFA


    FOLLOW_WS_in_query112 = frozenset([15, 23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_expression_in_query115 = frozenset([15])
    FOLLOW_WS_in_query117 = frozenset([15])
    FOLLOW_EOF_in_query120 = frozenset([1])
    FOLLOW_sequence_in_expression139 = frozenset([1, 15])
    FOLLOW_andOp_in_expression142 = frozenset([23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_sequence_in_expression144 = frozenset([1, 15])
    FOLLOW_factor_in_sequence170 = frozenset([1, 15])
    FOLLOW_WS_in_sequence173 = frozenset([15, 23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_factor_in_sequence176 = frozenset([1, 15])
    FOLLOW_term_in_factor202 = frozenset([1, 15])
    FOLLOW_orOp_in_factor205 = frozenset([23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_term_in_factor207 = frozenset([1, 15])
    FOLLOW_notOp_in_term231 = frozenset([23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_primitive_in_term233 = frozenset([1])
    FOLLOW_primitive_in_term247 = frozenset([1])
    FOLLOW_restriction_in_primitive263 = frozenset([1])
    FOLLOW_composite_in_primitive269 = frozenset([1])
    FOLLOW_item_in_primitive275 = frozenset([1])
    FOLLOW_comparable_in_restriction301 = frozenset([15, 16, 17, 18, 19, 20, 21, 22])
    FOLLOW_comparator_in_restriction303 = frozenset([23, 28, 29, 30, 31, 32, 33])
    FOLLOW_arg_in_restriction305 = frozenset([1])
    FOLLOW_WS_in_comparator329 = frozenset([15, 16, 17, 18, 19, 20, 21, 22])
    FOLLOW_LE_in_comparator335 = frozenset([1, 15])
    FOLLOW_LESSTHAN_in_comparator341 = frozenset([1, 15])
    FOLLOW_GE_in_comparator347 = frozenset([1, 15])
    FOLLOW_GT_in_comparator353 = frozenset([1, 15])
    FOLLOW_NE_in_comparator359 = frozenset([1, 15])
    FOLLOW_EQ_in_comparator365 = frozenset([1, 15])
    FOLLOW_HAS_in_comparator371 = frozenset([1, 15])
    FOLLOW_WS_in_comparator374 = frozenset([1, 15])
    FOLLOW_item_in_comparable396 = frozenset([1])
    FOLLOW_function_in_comparable402 = frozenset([1])
    FOLLOW_fnname_in_function417 = frozenset([23])
    FOLLOW_LPAREN_in_function419 = frozenset([23, 24, 28, 29, 30, 31, 32, 33])
    FOLLOW_arglist_in_function421 = frozenset([24])
    FOLLOW_RPAREN_in_function423 = frozenset([1])
    FOLLOW_arg_in_arglist452 = frozenset([1, 15, 44])
    FOLLOW_sep_in_arglist455 = frozenset([23, 28, 29, 30, 31, 32, 33])
    FOLLOW_arg_in_arglist457 = frozenset([1, 15, 44])
    FOLLOW_item_in_arg482 = frozenset([1])
    FOLLOW_composite_in_arg488 = frozenset([1])
    FOLLOW_function_in_arg494 = frozenset([1])
    FOLLOW_WS_in_andOp508 = frozenset([15, 25])
    FOLLOW_AND_in_andOp511 = frozenset([15])
    FOLLOW_WS_in_andOp513 = frozenset([1, 15])
    FOLLOW_WS_in_orOp528 = frozenset([15, 26])
    FOLLOW_OR_in_orOp531 = frozenset([15])
    FOLLOW_WS_in_orOp533 = frozenset([1, 15])
    FOLLOW_43_in_notOp548 = frozenset([1])
    FOLLOW_NOT_in_notOp554 = frozenset([15])
    FOLLOW_WS_in_notOp556 = frozenset([1, 15])
    FOLLOW_WS_in_sep571 = frozenset([15, 44])
    FOLLOW_44_in_sep574 = frozenset([1, 15])
    FOLLOW_WS_in_sep576 = frozenset([1, 15])
    FOLLOW_set_in_fnname0 = frozenset([1])
    FOLLOW_LPAREN_in_composite612 = frozenset([15, 23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_WS_in_composite614 = frozenset([15, 23, 27, 28, 29, 30, 31, 32, 33, 43])
    FOLLOW_expression_in_composite617 = frozenset([15, 24])
    FOLLOW_WS_in_composite619 = frozenset([15, 24])
    FOLLOW_RPAREN_in_composite622 = frozenset([1])
    FOLLOW_FIX_in_item642 = frozenset([28, 29, 30, 31, 32, 33])
    FOLLOW_value_in_item644 = frozenset([1])
    FOLLOW_REWRITE_in_item658 = frozenset([28, 29, 30, 31, 32, 33])
    FOLLOW_value_in_item660 = frozenset([1])
    FOLLOW_value_in_item674 = frozenset([1])
    FOLLOW_text_in_value692 = frozenset([1])
    FOLLOW_phrase_in_value708 = frozenset([1])
    FOLLOW_TEXT_in_text732 = frozenset([1])
    FOLLOW_DISTANCE_FN_in_text743 = frozenset([1])
    FOLLOW_GEO_POINT_FN_in_text756 = frozenset([1])
    FOLLOW_QUOTE_in_phrase775 = frozenset([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_set_in_phrase777 = frozenset([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44])
    FOLLOW_QUOTE_in_phrase793 = frozenset([1])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import ParserMain
    main = ParserMain("QueryLexer", QueryParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
