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


LT=19
EXPONENT=36
LETTER=40
OCTAL_ESC=44
FUZZY=6
FLOAT=27
NAME_START=38
NOT=33
AND=31
EOF=-1
LPAREN=25
WORD=14
HAS=7
RPAREN=26
NAME=16
ESC_SEQ=37
DIGIT=34
EQ=23
DOT=35
NE=22
GE=20
T__46=46
T__47=47
T__45=45
T__48=48
CONJUNCTION=4
UNICODE_ESC=43
NAME_MID=39
NUMBER=11
HEX_DIGIT=42
UNDERSCORE=41
LITERAL=8
INT=28
VALUE=15
TEXT=30
PHRASE=29
RESTRICTION=12
COLON=24
DISJUNCTION=5
WS=17
NEGATION=9
OR=32
GT=21
GLOBAL=10
LE=18
STRING=13


tokenNames = [
    "<invalid>", "<EOR>", "<DOWN>", "<UP>",
    "CONJUNCTION", "DISJUNCTION", "FUZZY", "HAS", "LITERAL", "NEGATION",
    "GLOBAL", "NUMBER", "RESTRICTION", "STRING", "WORD", "VALUE", "NAME",
    "WS", "LE", "LT", "GE", "GT", "NE", "EQ", "COLON", "LPAREN", "RPAREN",
    "FLOAT", "INT", "PHRASE", "TEXT", "AND", "OR", "NOT", "DIGIT", "DOT",
    "EXPONENT", "ESC_SEQ", "NAME_START", "NAME_MID", "LETTER", "UNDERSCORE",
    "HEX_DIGIT", "UNICODE_ESC", "OCTAL_ESC", "'+'", "'~'", "'-'", "','"
]




class QueryParser(Parser):
    grammarFileName = "blaze-out/host/genfiles/apphosting/api/search/genantlr/Query.g"
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

        self.dfa16 = self.DFA16(
            self, 16,
            eot = self.DFA16_eot,
            eof = self.DFA16_eof,
            min = self.DFA16_min,
            max = self.DFA16_max,
            accept = self.DFA16_accept,
            special = self.DFA16_special,
            transition = self.DFA16_transition
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

                self._state.following.append(self.FOLLOW_expression_in_query117)
                expression1 = self.expression()

                self._state.following.pop()
                self._adaptor.addChild(root_0, expression1.tree)
                EOF2=self.match(self.input, EOF, self.FOLLOW_EOF_in_query119)

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

        factor3 = None

        andOp4 = None

        factor5 = None


        stream_factor = RewriteRuleSubtreeStream(self._adaptor, "rule factor")
        stream_andOp = RewriteRuleSubtreeStream(self._adaptor, "rule andOp")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_factor_in_expression137)
                factor3 = self.factor()

                self._state.following.pop()
                stream_factor.add(factor3.tree)

                while True:
                    alt1 = 2
                    LA1_0 = self.input.LA(1)

                    if (LA1_0 == WS) :
                        alt1 = 1


                    if alt1 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_andOp_in_expression140)
                        andOp4 = self.andOp()

                        self._state.following.pop()
                        stream_andOp.add(andOp4.tree)
                        self._state.following.append(self.FOLLOW_factor_in_expression142)
                        factor5 = self.factor()

                        self._state.following.pop()
                        stream_factor.add(factor5.tree)


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

        term6 = None

        orOp7 = None

        term8 = None


        stream_orOp = RewriteRuleSubtreeStream(self._adaptor, "rule orOp")
        stream_term = RewriteRuleSubtreeStream(self._adaptor, "rule term")
        try:
            try:


                pass
                self._state.following.append(self.FOLLOW_term_in_factor170)
                term6 = self.term()

                self._state.following.pop()
                stream_term.add(term6.tree)

                while True:
                    alt2 = 2
                    alt2 = self.dfa2.predict(self.input)
                    if alt2 == 1:

                        pass
                        self._state.following.append(self.FOLLOW_orOp_in_factor173)
                        orOp7 = self.orOp()

                        self._state.following.pop()
                        stream_orOp.add(orOp7.tree)
                        self._state.following.append(self.FOLLOW_term_in_factor175)
                        term8 = self.term()

                        self._state.following.pop()
                        stream_term.add(term8.tree)


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

        notOp9 = None

        primitive10 = None

        primitive11 = None


        stream_notOp = RewriteRuleSubtreeStream(self._adaptor, "rule notOp")
        stream_primitive = RewriteRuleSubtreeStream(self._adaptor, "rule primitive")
        try:
            try:

                alt3 = 2
                LA3_0 = self.input.LA(1)

                if (LA3_0 == NOT or LA3_0 == 47) :
                    alt3 = 1
                elif (LA3_0 == NAME or (COLON <= LA3_0 <= LPAREN) or (FLOAT <= LA3_0 <= TEXT) or (45 <= LA3_0 <= 46)) :
                    alt3 = 2
                else:
                    nvae = NoViableAltException("", 3, 0, self.input)

                    raise nvae

                if alt3 == 1:

                    pass
                    self._state.following.append(self.FOLLOW_notOp_in_term204)
                    notOp9 = self.notOp()

                    self._state.following.pop()
                    stream_notOp.add(notOp9.tree)
                    self._state.following.append(self.FOLLOW_primitive_in_term206)
                    primitive10 = self.primitive()

                    self._state.following.pop()
                    stream_primitive.add(primitive10.tree)








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


                elif alt3 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_primitive_in_term220)
                    primitive11 = self.primitive()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, primitive11.tree)


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

        restrict12 = None

        atom13 = None


        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        try:
            try:

                alt4 = 2
                alt4 = self.dfa4.predict(self.input)
                if alt4 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_restrict_in_primitive239)
                    restrict12 = self.restrict()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, restrict12.tree)


                elif alt4 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_atom_in_primitive245)
                    atom13 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom13.tree)








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

        fieldname = None
        WS14 = None
        LE15 = None
        WS16 = None
        WS18 = None
        LT19 = None
        WS20 = None
        WS22 = None
        GE23 = None
        WS24 = None
        WS26 = None
        GT27 = None
        WS28 = None
        WS30 = None
        NE31 = None
        WS32 = None
        WS34 = None
        EQ35 = None
        WS36 = None
        COLON38 = None
        atom17 = None

        atom21 = None

        atom25 = None

        atom29 = None

        atom33 = None

        atom37 = None

        atom39 = None


        fieldname_tree = None
        WS14_tree = None
        LE15_tree = None
        WS16_tree = None
        WS18_tree = None
        LT19_tree = None
        WS20_tree = None
        WS22_tree = None
        GE23_tree = None
        WS24_tree = None
        WS26_tree = None
        GT27_tree = None
        WS28_tree = None
        WS30_tree = None
        NE31_tree = None
        WS32_tree = None
        WS34_tree = None
        EQ35_tree = None
        WS36_tree = None
        COLON38_tree = None
        stream_COLON = RewriteRuleTokenStream(self._adaptor, "token COLON")
        stream_GT = RewriteRuleTokenStream(self._adaptor, "token GT")
        stream_GE = RewriteRuleTokenStream(self._adaptor, "token GE")
        stream_LT = RewriteRuleTokenStream(self._adaptor, "token LT")
        stream_NAME = RewriteRuleTokenStream(self._adaptor, "token NAME")
        stream_WS = RewriteRuleTokenStream(self._adaptor, "token WS")
        stream_EQ = RewriteRuleTokenStream(self._adaptor, "token EQ")
        stream_LE = RewriteRuleTokenStream(self._adaptor, "token LE")
        stream_NE = RewriteRuleTokenStream(self._adaptor, "token NE")
        stream_atom = RewriteRuleSubtreeStream(self._adaptor, "rule atom")
        try:
            try:

                alt16 = 7
                alt16 = self.dfa16.predict(self.input)
                if alt16 == 1:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict274)
                    stream_NAME.add(fieldname)

                    while True:
                        alt5 = 2
                        LA5_0 = self.input.LA(1)

                        if (LA5_0 == WS) :
                            alt5 = 1


                        if alt5 == 1:

                            pass
                            WS14=self.match(self.input, WS, self.FOLLOW_WS_in_restrict276)
                            stream_WS.add(WS14)


                        else:
                            break


                    LE15=self.match(self.input, LE, self.FOLLOW_LE_in_restrict279)
                    stream_LE.add(LE15)

                    while True:
                        alt6 = 2
                        LA6_0 = self.input.LA(1)

                        if (LA6_0 == WS) :
                            alt6 = 1


                        if alt6 == 1:

                            pass
                            WS16=self.match(self.input, WS, self.FOLLOW_WS_in_restrict281)
                            stream_WS.add(WS16)


                        else:
                            break


                    self._state.following.append(self.FOLLOW_atom_in_restrict284)
                    atom17 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom17.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(stream_LE.nextNode(), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt16 == 2:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict307)
                    stream_NAME.add(fieldname)

                    while True:
                        alt7 = 2
                        LA7_0 = self.input.LA(1)

                        if (LA7_0 == WS) :
                            alt7 = 1


                        if alt7 == 1:

                            pass
                            WS18=self.match(self.input, WS, self.FOLLOW_WS_in_restrict309)
                            stream_WS.add(WS18)


                        else:
                            break


                    LT19=self.match(self.input, LT, self.FOLLOW_LT_in_restrict312)
                    stream_LT.add(LT19)

                    while True:
                        alt8 = 2
                        LA8_0 = self.input.LA(1)

                        if (LA8_0 == WS) :
                            alt8 = 1


                        if alt8 == 1:

                            pass
                            WS20=self.match(self.input, WS, self.FOLLOW_WS_in_restrict314)
                            stream_WS.add(WS20)


                        else:
                            break


                    self._state.following.append(self.FOLLOW_atom_in_restrict317)
                    atom21 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom21.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(stream_LT.nextNode(), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt16 == 3:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict340)
                    stream_NAME.add(fieldname)

                    while True:
                        alt9 = 2
                        LA9_0 = self.input.LA(1)

                        if (LA9_0 == WS) :
                            alt9 = 1


                        if alt9 == 1:

                            pass
                            WS22=self.match(self.input, WS, self.FOLLOW_WS_in_restrict342)
                            stream_WS.add(WS22)


                        else:
                            break


                    GE23=self.match(self.input, GE, self.FOLLOW_GE_in_restrict345)
                    stream_GE.add(GE23)

                    while True:
                        alt10 = 2
                        LA10_0 = self.input.LA(1)

                        if (LA10_0 == WS) :
                            alt10 = 1


                        if alt10 == 1:

                            pass
                            WS24=self.match(self.input, WS, self.FOLLOW_WS_in_restrict347)
                            stream_WS.add(WS24)


                        else:
                            break


                    self._state.following.append(self.FOLLOW_atom_in_restrict350)
                    atom25 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom25.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(stream_GE.nextNode(), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt16 == 4:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict373)
                    stream_NAME.add(fieldname)

                    while True:
                        alt11 = 2
                        LA11_0 = self.input.LA(1)

                        if (LA11_0 == WS) :
                            alt11 = 1


                        if alt11 == 1:

                            pass
                            WS26=self.match(self.input, WS, self.FOLLOW_WS_in_restrict375)
                            stream_WS.add(WS26)


                        else:
                            break


                    GT27=self.match(self.input, GT, self.FOLLOW_GT_in_restrict378)
                    stream_GT.add(GT27)

                    while True:
                        alt12 = 2
                        LA12_0 = self.input.LA(1)

                        if (LA12_0 == WS) :
                            alt12 = 1


                        if alt12 == 1:

                            pass
                            WS28=self.match(self.input, WS, self.FOLLOW_WS_in_restrict380)
                            stream_WS.add(WS28)


                        else:
                            break


                    self._state.following.append(self.FOLLOW_atom_in_restrict383)
                    atom29 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom29.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(stream_GT.nextNode(), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt16 == 5:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict406)
                    stream_NAME.add(fieldname)

                    while True:
                        alt13 = 2
                        LA13_0 = self.input.LA(1)

                        if (LA13_0 == WS) :
                            alt13 = 1


                        if alt13 == 1:

                            pass
                            WS30=self.match(self.input, WS, self.FOLLOW_WS_in_restrict408)
                            stream_WS.add(WS30)


                        else:
                            break


                    NE31=self.match(self.input, NE, self.FOLLOW_NE_in_restrict411)
                    stream_NE.add(NE31)

                    while True:
                        alt14 = 2
                        LA14_0 = self.input.LA(1)

                        if (LA14_0 == WS) :
                            alt14 = 1


                        if alt14 == 1:

                            pass
                            WS32=self.match(self.input, WS, self.FOLLOW_WS_in_restrict413)
                            stream_WS.add(WS32)


                        else:
                            break


                    self._state.following.append(self.FOLLOW_atom_in_restrict416)
                    atom33 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom33.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(stream_NE.nextNode(), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt16 == 6:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict439)
                    stream_NAME.add(fieldname)

                    while True:
                        alt15 = 2
                        LA15_0 = self.input.LA(1)

                        if (LA15_0 == WS) :
                            alt15 = 1


                        if alt15 == 1:

                            pass
                            WS34=self.match(self.input, WS, self.FOLLOW_WS_in_restrict441)
                            stream_WS.add(WS34)


                        else:
                            break


                    EQ35=self.match(self.input, EQ, self.FOLLOW_EQ_in_restrict444)
                    stream_EQ.add(EQ35)
                    WS36=self.match(self.input, WS, self.FOLLOW_WS_in_restrict446)
                    stream_WS.add(WS36)
                    self._state.following.append(self.FOLLOW_atom_in_restrict448)
                    atom37 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom37.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(stream_EQ.nextNode(), root_2)

                    self._adaptor.addChild(root_2, stream_atom.nextTree())

                    self._adaptor.addChild(root_1, root_2)

                    self._adaptor.addChild(root_0, root_1)



                    retval.tree = root_0


                elif alt16 == 7:

                    pass
                    fieldname=self.match(self.input, NAME, self.FOLLOW_NAME_in_restrict472)
                    stream_NAME.add(fieldname)
                    COLON38=self.match(self.input, COLON, self.FOLLOW_COLON_in_restrict474)
                    stream_COLON.add(COLON38)
                    self._state.following.append(self.FOLLOW_atom_in_restrict476)
                    atom39 = self.atom()

                    self._state.following.pop()
                    stream_atom.add(atom39.tree)








                    retval.tree = root_0
                    stream_fieldname = RewriteRuleTokenStream(self._adaptor, "token fieldname", fieldname)

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(RESTRICTION, "RESTRICTION"), root_1)

                    self._adaptor.addChild(root_1, stream_fieldname.nextNode())

                    root_2 = self._adaptor.nil()
                    root_2 = self._adaptor.becomeRoot(self._adaptor.createFromType(HAS, "HAS"), root_2)

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



    class atom_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def atom(self, ):

        retval = self.atom_return()
        retval.start = self.input.LT(1)

        root_0 = None

        LPAREN41 = None
        RPAREN43 = None
        value40 = None

        expression42 = None


        LPAREN41_tree = None
        RPAREN43_tree = None
        stream_RPAREN = RewriteRuleTokenStream(self._adaptor, "token RPAREN")
        stream_LPAREN = RewriteRuleTokenStream(self._adaptor, "token LPAREN")
        stream_expression = RewriteRuleSubtreeStream(self._adaptor, "rule expression")
        try:
            try:

                alt17 = 2
                LA17_0 = self.input.LA(1)

                if (LA17_0 == NAME or LA17_0 == COLON or (FLOAT <= LA17_0 <= TEXT) or (45 <= LA17_0 <= 46)) :
                    alt17 = 1
                elif (LA17_0 == LPAREN) :
                    alt17 = 2
                else:
                    nvae = NoViableAltException("", 17, 0, self.input)

                    raise nvae

                if alt17 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_value_in_atom505)
                    value40 = self.value()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, value40.tree)


                elif alt17 == 2:

                    pass
                    LPAREN41=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_atom511)
                    stream_LPAREN.add(LPAREN41)
                    self._state.following.append(self.FOLLOW_expression_in_atom513)
                    expression42 = self.expression()

                    self._state.following.pop()
                    stream_expression.add(expression42.tree)
                    RPAREN43=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_atom515)
                    stream_RPAREN.add(RPAREN43)








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

        text_value44 = None

        numeric_value45 = None


        stream_numeric_value = RewriteRuleSubtreeStream(self._adaptor, "rule numeric_value")
        try:
            try:

                alt18 = 2
                LA18_0 = self.input.LA(1)

                if (LA18_0 == NAME or LA18_0 == COLON or (PHRASE <= LA18_0 <= TEXT) or (45 <= LA18_0 <= 46)) :
                    alt18 = 1
                elif ((FLOAT <= LA18_0 <= INT)) :
                    alt18 = 2
                else:
                    nvae = NoViableAltException("", 18, 0, self.input)

                    raise nvae

                if alt18 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_text_value_in_value533)
                    text_value44 = self.text_value()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, text_value44.tree)


                elif alt18 == 2:

                    pass
                    self._state.following.append(self.FOLLOW_numeric_value_in_value539)
                    numeric_value45 = self.numeric_value()

                    self._state.following.pop()
                    stream_numeric_value.add(numeric_value45.tree)








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

        set46 = None

        set46_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                set46 = self.input.LT(1)
                if (FLOAT <= self.input.LA(1) <= INT):
                    self.input.consume()
                    self._adaptor.addChild(root_0, self._adaptor.createWithPayload(set46))
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

        literal_text47 = None

        rewritable_text48 = None

        text49 = None



        try:
            try:

                alt19 = 3
                LA19 = self.input.LA(1)
                if LA19 == 45:
                    alt19 = 1
                elif LA19 == 46:
                    alt19 = 2
                elif LA19 == NAME or LA19 == COLON or LA19 == PHRASE or LA19 == TEXT:
                    alt19 = 3
                else:
                    nvae = NoViableAltException("", 19, 0, self.input)

                    raise nvae

                if alt19 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_literal_text_in_text_value581)
                    literal_text47 = self.literal_text()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, literal_text47.tree)


                elif alt19 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_rewritable_text_in_text_value587)
                    rewritable_text48 = self.rewritable_text()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, rewritable_text48.tree)


                elif alt19 == 3:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_text_in_text_value593)
                    text49 = self.text()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, text49.tree)


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

        char_literal50 = None
        text51 = None


        char_literal50_tree = None
        stream_45 = RewriteRuleTokenStream(self._adaptor, "token 45")
        stream_text = RewriteRuleSubtreeStream(self._adaptor, "rule text")
        try:
            try:


                pass
                char_literal50=self.match(self.input, 45, self.FOLLOW_45_in_literal_text606)
                stream_45.add(char_literal50)
                self._state.following.append(self.FOLLOW_text_in_literal_text608)
                text51 = self.text()

                self._state.following.pop()
                stream_text.add(text51.tree)








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

        char_literal52 = None
        text53 = None


        char_literal52_tree = None
        stream_46 = RewriteRuleTokenStream(self._adaptor, "token 46")
        stream_text = RewriteRuleSubtreeStream(self._adaptor, "rule text")
        try:
            try:


                pass
                char_literal52=self.match(self.input, 46, self.FOLLOW_46_in_rewritable_text628)
                stream_46.add(char_literal52)
                self._state.following.append(self.FOLLOW_text_in_rewritable_text630)
                text53 = self.text()

                self._state.following.pop()
                stream_text.add(text53.tree)








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
        char_literal54 = None

        n_tree = None
        s_tree = None
        t_tree = None
        char_literal54_tree = None
        stream_COLON = RewriteRuleTokenStream(self._adaptor, "token COLON")
        stream_NAME = RewriteRuleTokenStream(self._adaptor, "token NAME")
        stream_TEXT = RewriteRuleTokenStream(self._adaptor, "token TEXT")
        stream_PHRASE = RewriteRuleTokenStream(self._adaptor, "token PHRASE")

        try:
            try:

                alt20 = 4
                LA20 = self.input.LA(1)
                if LA20 == NAME:
                    alt20 = 1
                elif LA20 == PHRASE:
                    alt20 = 2
                elif LA20 == TEXT:
                    alt20 = 3
                elif LA20 == COLON:
                    alt20 = 4
                else:
                    nvae = NoViableAltException("", 20, 0, self.input)

                    raise nvae

                if alt20 == 1:

                    pass
                    n=self.match(self.input, NAME, self.FOLLOW_NAME_in_text652)
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


                elif alt20 == 2:

                    pass
                    s=self.match(self.input, PHRASE, self.FOLLOW_PHRASE_in_text671)
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


                elif alt20 == 3:

                    pass
                    t=self.match(self.input, TEXT, self.FOLLOW_TEXT_in_text690)
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


                elif alt20 == 4:

                    pass
                    char_literal54=self.match(self.input, COLON, self.FOLLOW_COLON_in_text707)
                    stream_COLON.add(char_literal54)








                    retval.tree = root_0

                    if retval is not None:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", retval.tree)
                    else:
                        stream_retval = RewriteRuleSubtreeStream(self._adaptor, "token retval", None)


                    root_0 = self._adaptor.nil()


                    root_1 = self._adaptor.nil()
                    root_1 = self._adaptor.becomeRoot(self._adaptor.createFromType(VALUE, "VALUE"), root_1)

                    self._adaptor.addChild(root_1, self._adaptor.createFromType(WORD, "WORD"))
                    self._adaptor.addChild(root_1, stream_COLON.nextNode())

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



    class name_return(ParserRuleReturnScope):
        def __init__(self):
            ParserRuleReturnScope.__init__(self)

            self.tree = None






    def name(self, ):

        retval = self.name_return()
        retval.start = self.input.LT(1)

        root_0 = None

        NAME55 = None

        NAME55_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                NAME55=self.match(self.input, NAME, self.FOLLOW_NAME_in_name730)

                NAME55_tree = self._adaptor.createWithPayload(NAME55)
                self._adaptor.addChild(root_0, NAME55_tree)




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

        LPAREN57 = None
        RPAREN59 = None
        name56 = None

        arglist58 = None


        LPAREN57_tree = None
        RPAREN59_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_name_in_function743)
                name56 = self.name()

                self._state.following.pop()
                self._adaptor.addChild(root_0, name56.tree)
                LPAREN57=self.match(self.input, LPAREN, self.FOLLOW_LPAREN_in_function745)

                LPAREN57_tree = self._adaptor.createWithPayload(LPAREN57)
                self._adaptor.addChild(root_0, LPAREN57_tree)

                self._state.following.append(self.FOLLOW_arglist_in_function747)
                arglist58 = self.arglist()

                self._state.following.pop()
                self._adaptor.addChild(root_0, arglist58.tree)
                RPAREN59=self.match(self.input, RPAREN, self.FOLLOW_RPAREN_in_function749)

                RPAREN59_tree = self._adaptor.createWithPayload(RPAREN59)
                self._adaptor.addChild(root_0, RPAREN59_tree)




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

        arg60 = None

        sep61 = None

        arg62 = None



        try:
            try:

                alt22 = 2
                LA22_0 = self.input.LA(1)

                if (LA22_0 == NAME or (COLON <= LA22_0 <= LPAREN) or (FLOAT <= LA22_0 <= TEXT) or (45 <= LA22_0 <= 46)) :
                    alt22 = 1
                elif (LA22_0 == RPAREN) :
                    alt22 = 2
                else:
                    nvae = NoViableAltException("", 22, 0, self.input)

                    raise nvae

                if alt22 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    self._state.following.append(self.FOLLOW_arg_in_arglist762)
                    arg60 = self.arg()

                    self._state.following.pop()
                    self._adaptor.addChild(root_0, arg60.tree)

                    while True:
                        alt21 = 2
                        LA21_0 = self.input.LA(1)

                        if (LA21_0 == WS or LA21_0 == 48) :
                            alt21 = 1


                        if alt21 == 1:

                            pass
                            self._state.following.append(self.FOLLOW_sep_in_arglist765)
                            sep61 = self.sep()

                            self._state.following.pop()
                            self._adaptor.addChild(root_0, sep61.tree)
                            self._state.following.append(self.FOLLOW_arg_in_arglist767)
                            arg62 = self.arg()

                            self._state.following.pop()
                            self._adaptor.addChild(root_0, arg62.tree)


                        else:
                            break




                elif alt22 == 2:

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

        atom63 = None



        try:
            try:


                pass
                root_0 = self._adaptor.nil()

                self._state.following.append(self.FOLLOW_atom_in_arg786)
                atom63 = self.atom()

                self._state.following.pop()
                self._adaptor.addChild(root_0, atom63.tree)



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

        WS64 = None
        AND65 = None
        WS66 = None

        WS64_tree = None
        AND65_tree = None
        WS66_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                cnt23 = 0
                while True:
                    alt23 = 2
                    LA23_0 = self.input.LA(1)

                    if (LA23_0 == WS) :
                        alt23 = 1


                    if alt23 == 1:

                        pass
                        WS64=self.match(self.input, WS, self.FOLLOW_WS_in_andOp799)

                        WS64_tree = self._adaptor.createWithPayload(WS64)
                        self._adaptor.addChild(root_0, WS64_tree)



                    else:
                        if cnt23 >= 1:
                            break

                        eee = EarlyExitException(23, self.input)
                        raise eee

                    cnt23 += 1



                alt25 = 2
                LA25_0 = self.input.LA(1)

                if (LA25_0 == AND) :
                    alt25 = 1
                if alt25 == 1:

                    pass
                    AND65=self.match(self.input, AND, self.FOLLOW_AND_in_andOp803)

                    AND65_tree = self._adaptor.createWithPayload(AND65)
                    self._adaptor.addChild(root_0, AND65_tree)


                    cnt24 = 0
                    while True:
                        alt24 = 2
                        LA24_0 = self.input.LA(1)

                        if (LA24_0 == WS) :
                            alt24 = 1


                        if alt24 == 1:

                            pass
                            WS66=self.match(self.input, WS, self.FOLLOW_WS_in_andOp805)

                            WS66_tree = self._adaptor.createWithPayload(WS66)
                            self._adaptor.addChild(root_0, WS66_tree)



                        else:
                            if cnt24 >= 1:
                                break

                            eee = EarlyExitException(24, self.input)
                            raise eee

                        cnt24 += 1








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

        WS67 = None
        OR68 = None
        WS69 = None

        WS67_tree = None
        OR68_tree = None
        WS69_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                cnt26 = 0
                while True:
                    alt26 = 2
                    LA26_0 = self.input.LA(1)

                    if (LA26_0 == WS) :
                        alt26 = 1


                    if alt26 == 1:

                        pass
                        WS67=self.match(self.input, WS, self.FOLLOW_WS_in_orOp821)

                        WS67_tree = self._adaptor.createWithPayload(WS67)
                        self._adaptor.addChild(root_0, WS67_tree)



                    else:
                        if cnt26 >= 1:
                            break

                        eee = EarlyExitException(26, self.input)
                        raise eee

                    cnt26 += 1


                OR68=self.match(self.input, OR, self.FOLLOW_OR_in_orOp824)

                OR68_tree = self._adaptor.createWithPayload(OR68)
                self._adaptor.addChild(root_0, OR68_tree)


                cnt27 = 0
                while True:
                    alt27 = 2
                    LA27_0 = self.input.LA(1)

                    if (LA27_0 == WS) :
                        alt27 = 1


                    if alt27 == 1:

                        pass
                        WS69=self.match(self.input, WS, self.FOLLOW_WS_in_orOp826)

                        WS69_tree = self._adaptor.createWithPayload(WS69)
                        self._adaptor.addChild(root_0, WS69_tree)



                    else:
                        if cnt27 >= 1:
                            break

                        eee = EarlyExitException(27, self.input)
                        raise eee

                    cnt27 += 1





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

        char_literal70 = None
        NOT71 = None
        WS72 = None

        char_literal70_tree = None
        NOT71_tree = None
        WS72_tree = None

        try:
            try:

                alt29 = 2
                LA29_0 = self.input.LA(1)

                if (LA29_0 == 47) :
                    alt29 = 1
                elif (LA29_0 == NOT) :
                    alt29 = 2
                else:
                    nvae = NoViableAltException("", 29, 0, self.input)

                    raise nvae

                if alt29 == 1:

                    pass
                    root_0 = self._adaptor.nil()

                    char_literal70=self.match(self.input, 47, self.FOLLOW_47_in_notOp840)

                    char_literal70_tree = self._adaptor.createWithPayload(char_literal70)
                    self._adaptor.addChild(root_0, char_literal70_tree)



                elif alt29 == 2:

                    pass
                    root_0 = self._adaptor.nil()

                    NOT71=self.match(self.input, NOT, self.FOLLOW_NOT_in_notOp846)

                    NOT71_tree = self._adaptor.createWithPayload(NOT71)
                    self._adaptor.addChild(root_0, NOT71_tree)


                    cnt28 = 0
                    while True:
                        alt28 = 2
                        LA28_0 = self.input.LA(1)

                        if (LA28_0 == WS) :
                            alt28 = 1


                        if alt28 == 1:

                            pass
                            WS72=self.match(self.input, WS, self.FOLLOW_WS_in_notOp848)

                            WS72_tree = self._adaptor.createWithPayload(WS72)
                            self._adaptor.addChild(root_0, WS72_tree)



                        else:
                            if cnt28 >= 1:
                                break

                            eee = EarlyExitException(28, self.input)
                            raise eee

                        cnt28 += 1




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

        WS73 = None
        char_literal74 = None
        WS75 = None

        WS73_tree = None
        char_literal74_tree = None
        WS75_tree = None

        try:
            try:


                pass
                root_0 = self._adaptor.nil()


                while True:
                    alt30 = 2
                    LA30_0 = self.input.LA(1)

                    if (LA30_0 == WS) :
                        alt30 = 1


                    if alt30 == 1:

                        pass
                        WS73=self.match(self.input, WS, self.FOLLOW_WS_in_sep862)

                        WS73_tree = self._adaptor.createWithPayload(WS73)
                        self._adaptor.addChild(root_0, WS73_tree)



                    else:
                        break


                char_literal74=self.match(self.input, 48, self.FOLLOW_48_in_sep865)

                char_literal74_tree = self._adaptor.createWithPayload(char_literal74)
                self._adaptor.addChild(root_0, char_literal74_tree)


                while True:
                    alt31 = 2
                    LA31_0 = self.input.LA(1)

                    if (LA31_0 == WS) :
                        alt31 = 1


                    if alt31 == 1:

                        pass
                        WS75=self.match(self.input, WS, self.FOLLOW_WS_in_sep867)

                        WS75_tree = self._adaptor.createWithPayload(WS75)
                        self._adaptor.addChild(root_0, WS75_tree)



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
        u"\1\2\3\uffff"
        )

    DFA2_min = DFA.unpack(
        u"\1\21\1\20\2\uffff"
        )

    DFA2_max = DFA.unpack(
        u"\1\32\1\57\2\uffff"
        )

    DFA2_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1"
        )

    DFA2_special = DFA.unpack(
        u"\4\uffff"
        )


    DFA2_transition = [
        DFA.unpack(u"\1\1\10\uffff\1\2"),
        DFA.unpack(u"\1\2\1\1\6\uffff\2\2\1\uffff\5\2\1\3\1\2\13\uffff\3"
        u"\2"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA2 = DFA


    DFA4_eot = DFA.unpack(
        u"\5\uffff"
        )

    DFA4_eof = DFA.unpack(
        u"\1\uffff\1\2\3\uffff"
        )

    DFA4_min = DFA.unpack(
        u"\1\20\1\21\2\uffff\1\20"
        )

    DFA4_max = DFA.unpack(
        u"\1\56\1\32\2\uffff\1\57"
        )

    DFA4_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1\1\uffff"
        )

    DFA4_special = DFA.unpack(
        u"\5\uffff"
        )


    DFA4_transition = [
        DFA.unpack(u"\1\1\7\uffff\2\2\1\uffff\4\2\16\uffff\2\2"),
        DFA.unpack(u"\1\4\7\3\1\uffff\1\2"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\2\1\4\6\3\2\2\1\uffff\7\2\13\uffff\3\2")
    ]



    DFA4 = DFA


    DFA16_eot = DFA.unpack(
        u"\12\uffff"
        )

    DFA16_eof = DFA.unpack(
        u"\12\uffff"
        )

    DFA16_min = DFA.unpack(
        u"\1\20\1\21\1\uffff\1\21\6\uffff"
        )

    DFA16_max = DFA.unpack(
        u"\1\20\1\30\1\uffff\1\27\6\uffff"
        )

    DFA16_accept = DFA.unpack(
        u"\2\uffff\1\7\1\uffff\1\5\1\6\1\2\1\3\1\4\1\1"
        )

    DFA16_special = DFA.unpack(
        u"\12\uffff"
        )


    DFA16_transition = [
        DFA.unpack(u"\1\1"),
        DFA.unpack(u"\1\3\1\11\1\6\1\7\1\10\1\4\1\5\1\2"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\3\1\11\1\6\1\7\1\10\1\4\1\5"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA16 = DFA


    FOLLOW_expression_in_query117 = frozenset([])
    FOLLOW_EOF_in_query119 = frozenset([1])
    FOLLOW_factor_in_expression137 = frozenset([1, 17])
    FOLLOW_andOp_in_expression140 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_factor_in_expression142 = frozenset([1, 17])
    FOLLOW_term_in_factor170 = frozenset([1, 17])
    FOLLOW_orOp_in_factor173 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_term_in_factor175 = frozenset([1, 17])
    FOLLOW_notOp_in_term204 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_primitive_in_term206 = frozenset([1])
    FOLLOW_primitive_in_term220 = frozenset([1])
    FOLLOW_restrict_in_primitive239 = frozenset([1])
    FOLLOW_atom_in_primitive245 = frozenset([1])
    FOLLOW_NAME_in_restrict274 = frozenset([17, 18])
    FOLLOW_WS_in_restrict276 = frozenset([17, 18])
    FOLLOW_LE_in_restrict279 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_WS_in_restrict281 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict284 = frozenset([1])
    FOLLOW_NAME_in_restrict307 = frozenset([17, 19])
    FOLLOW_WS_in_restrict309 = frozenset([17, 19])
    FOLLOW_LT_in_restrict312 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_WS_in_restrict314 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict317 = frozenset([1])
    FOLLOW_NAME_in_restrict340 = frozenset([17, 20])
    FOLLOW_WS_in_restrict342 = frozenset([17, 20])
    FOLLOW_GE_in_restrict345 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_WS_in_restrict347 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict350 = frozenset([1])
    FOLLOW_NAME_in_restrict373 = frozenset([17, 21])
    FOLLOW_WS_in_restrict375 = frozenset([17, 21])
    FOLLOW_GT_in_restrict378 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_WS_in_restrict380 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict383 = frozenset([1])
    FOLLOW_NAME_in_restrict406 = frozenset([17, 22])
    FOLLOW_WS_in_restrict408 = frozenset([17, 22])
    FOLLOW_NE_in_restrict411 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_WS_in_restrict413 = frozenset([16, 17, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict416 = frozenset([1])
    FOLLOW_NAME_in_restrict439 = frozenset([17, 23])
    FOLLOW_WS_in_restrict441 = frozenset([17, 23])
    FOLLOW_EQ_in_restrict444 = frozenset([17])
    FOLLOW_WS_in_restrict446 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict448 = frozenset([1])
    FOLLOW_NAME_in_restrict472 = frozenset([24])
    FOLLOW_COLON_in_restrict474 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_atom_in_restrict476 = frozenset([1])
    FOLLOW_value_in_atom505 = frozenset([1])
    FOLLOW_LPAREN_in_atom511 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_expression_in_atom513 = frozenset([26])
    FOLLOW_RPAREN_in_atom515 = frozenset([1])
    FOLLOW_text_value_in_value533 = frozenset([1])
    FOLLOW_numeric_value_in_value539 = frozenset([1])
    FOLLOW_set_in_numeric_value0 = frozenset([1])
    FOLLOW_literal_text_in_text_value581 = frozenset([1])
    FOLLOW_rewritable_text_in_text_value587 = frozenset([1])
    FOLLOW_text_in_text_value593 = frozenset([1])
    FOLLOW_45_in_literal_text606 = frozenset([16, 24, 29, 30, 45, 46])
    FOLLOW_text_in_literal_text608 = frozenset([1])
    FOLLOW_46_in_rewritable_text628 = frozenset([16, 24, 29, 30, 45, 46])
    FOLLOW_text_in_rewritable_text630 = frozenset([1])
    FOLLOW_NAME_in_text652 = frozenset([1])
    FOLLOW_PHRASE_in_text671 = frozenset([1])
    FOLLOW_TEXT_in_text690 = frozenset([1])
    FOLLOW_COLON_in_text707 = frozenset([1])
    FOLLOW_NAME_in_name730 = frozenset([1])
    FOLLOW_name_in_function743 = frozenset([25])
    FOLLOW_LPAREN_in_function745 = frozenset([16, 24, 25, 26, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_arglist_in_function747 = frozenset([26])
    FOLLOW_RPAREN_in_function749 = frozenset([1])
    FOLLOW_arg_in_arglist762 = frozenset([1, 17, 48])
    FOLLOW_sep_in_arglist765 = frozenset([16, 24, 25, 27, 28, 29, 30, 33, 45, 46, 47])
    FOLLOW_arg_in_arglist767 = frozenset([1, 17, 48])
    FOLLOW_atom_in_arg786 = frozenset([1])
    FOLLOW_WS_in_andOp799 = frozenset([1, 17, 31])
    FOLLOW_AND_in_andOp803 = frozenset([17])
    FOLLOW_WS_in_andOp805 = frozenset([1, 17])
    FOLLOW_WS_in_orOp821 = frozenset([17, 32])
    FOLLOW_OR_in_orOp824 = frozenset([17])
    FOLLOW_WS_in_orOp826 = frozenset([1, 17])
    FOLLOW_47_in_notOp840 = frozenset([1])
    FOLLOW_NOT_in_notOp846 = frozenset([17])
    FOLLOW_WS_in_notOp848 = frozenset([1, 17])
    FOLLOW_WS_in_sep862 = frozenset([17, 48])
    FOLLOW_48_in_sep865 = frozenset([1, 17])
    FOLLOW_WS_in_sep867 = frozenset([1, 17])



def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import ParserMain
    main = ParserMain("QueryLexer", QueryParser)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
