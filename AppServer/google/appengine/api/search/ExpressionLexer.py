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


class ExpressionLexer(Lexer):

    grammarFileName = "blaze-out/host/genfiles/apphosting/api/search/genantlr/Expression.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"

    def __init__(self, input=None, state=None):
        if state is None:
            state = RecognizerSharedState()
        Lexer.__init__(self, input, state)

        self.dfa9 = self.DFA9(
            self, 9,
            eot = self.DFA9_eot,
            eof = self.DFA9_eof,
            min = self.DFA9_min,
            max = self.DFA9_max,
            accept = self.DFA9_accept,
            special = self.DFA9_special,
            transition = self.DFA9_transition
            )

        self.dfa14 = self.DFA14(
            self, 14,
            eot = self.DFA14_eot,
            eof = self.DFA14_eof,
            min = self.DFA14_min,
            max = self.DFA14_max,
            accept = self.DFA14_accept,
            special = self.DFA14_special,
            transition = self.DFA14_transition
            )







    def mT__32(self, ):

        try:
            _type = T__32
            _channel = DEFAULT_CHANNEL



            pass
            self.match(46)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__33(self, ):

        try:
            _type = T__33
            _channel = DEFAULT_CHANNEL



            pass
            self.match(44)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__34(self, ):

        try:
            _type = T__34
            _channel = DEFAULT_CHANNEL



            pass
            self.match("abs")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__35(self, ):

        try:
            _type = T__35
            _channel = DEFAULT_CHANNEL



            pass
            self.match("count")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__36(self, ):

        try:
            _type = T__36
            _channel = DEFAULT_CHANNEL



            pass
            self.match("if")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__37(self, ):

        try:
            _type = T__37
            _channel = DEFAULT_CHANNEL



            pass
            self.match("kilometers")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__38(self, ):

        try:
            _type = T__38
            _channel = DEFAULT_CHANNEL



            pass
            self.match("len")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__39(self, ):

        try:
            _type = T__39
            _channel = DEFAULT_CHANNEL



            pass
            self.match("log")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__40(self, ):

        try:
            _type = T__40
            _channel = DEFAULT_CHANNEL



            pass
            self.match("max")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__41(self, ):

        try:
            _type = T__41
            _channel = DEFAULT_CHANNEL



            pass
            self.match("miles")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__42(self, ):

        try:
            _type = T__42
            _channel = DEFAULT_CHANNEL



            pass
            self.match("min")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__43(self, ):

        try:
            _type = T__43
            _channel = DEFAULT_CHANNEL



            pass
            self.match("pow")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__44(self, ):

        try:
            _type = T__44
            _channel = DEFAULT_CHANNEL



            pass
            self.match("snippet")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mINT(self, ):

        try:
            _type = INT
            _channel = DEFAULT_CHANNEL



            pass

            cnt1 = 0
            while True:
                alt1 = 2
                LA1_0 = self.input.LA(1)

                if ((48 <= LA1_0 <= 57)) :
                    alt1 = 1


                if alt1 == 1:

                    pass
                    self.mDIGIT()


                else:
                    if cnt1 >= 1:
                        break

                    eee = EarlyExitException(1, self.input)
                    raise eee

                cnt1 += 1





            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mPHRASE(self, ):

        try:
            _type = PHRASE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(34)

            while True:
                alt2 = 2
                LA2_0 = self.input.LA(1)

                if ((0 <= LA2_0 <= 33) or (35 <= LA2_0 <= 91) or (93 <= LA2_0 <= 65535)) :
                    alt2 = 1


                if alt2 == 1:

                    pass
                    if (0 <= self.input.LA(1) <= 33) or (35 <= self.input.LA(1) <= 91) or (93 <= self.input.LA(1) <= 65535):
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    break


            self.match(34)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFLOAT(self, ):

        try:
            _type = FLOAT
            _channel = DEFAULT_CHANNEL


            alt9 = 3
            alt9 = self.dfa9.predict(self.input)
            if alt9 == 1:

                pass

                cnt3 = 0
                while True:
                    alt3 = 2
                    LA3_0 = self.input.LA(1)

                    if ((48 <= LA3_0 <= 57)) :
                        alt3 = 1


                    if alt3 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt3 >= 1:
                            break

                        eee = EarlyExitException(3, self.input)
                        raise eee

                    cnt3 += 1


                self.match(46)

                while True:
                    alt4 = 2
                    LA4_0 = self.input.LA(1)

                    if ((48 <= LA4_0 <= 57)) :
                        alt4 = 1


                    if alt4 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        break



                alt5 = 2
                LA5_0 = self.input.LA(1)

                if (LA5_0 == 69 or LA5_0 == 101) :
                    alt5 = 1
                if alt5 == 1:

                    pass
                    self.mEXPONENT()





            elif alt9 == 2:

                pass
                self.match(46)

                cnt6 = 0
                while True:
                    alt6 = 2
                    LA6_0 = self.input.LA(1)

                    if ((48 <= LA6_0 <= 57)) :
                        alt6 = 1


                    if alt6 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt6 >= 1:
                            break

                        eee = EarlyExitException(6, self.input)
                        raise eee

                    cnt6 += 1



                alt7 = 2
                LA7_0 = self.input.LA(1)

                if (LA7_0 == 69 or LA7_0 == 101) :
                    alt7 = 1
                if alt7 == 1:

                    pass
                    self.mEXPONENT()





            elif alt9 == 3:

                pass

                cnt8 = 0
                while True:
                    alt8 = 2
                    LA8_0 = self.input.LA(1)

                    if ((48 <= LA8_0 <= 57)) :
                        alt8 = 1


                    if alt8 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt8 >= 1:
                            break

                        eee = EarlyExitException(8, self.input)
                        raise eee

                    cnt8 += 1


                self.mEXPONENT()


            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mNAME(self, ):

        try:
            _type = NAME
            _channel = DEFAULT_CHANNEL



            pass
            self.mNAME_START()

            while True:
                alt10 = 2
                LA10_0 = self.input.LA(1)

                if (LA10_0 == 36 or (48 <= LA10_0 <= 57) or (65 <= LA10_0 <= 90) or LA10_0 == 95 or (97 <= LA10_0 <= 122)) :
                    alt10 = 1


                if alt10 == 1:

                    pass
                    if self.input.LA(1) == 36 or (48 <= self.input.LA(1) <= 57) or (65 <= self.input.LA(1) <= 90) or self.input.LA(1) == 95 or (97 <= self.input.LA(1) <= 122):
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    break





            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLPAREN(self, ):

        try:
            _type = LPAREN
            _channel = DEFAULT_CHANNEL



            pass
            self.match(40)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mRPAREN(self, ):

        try:
            _type = RPAREN
            _channel = DEFAULT_CHANNEL



            pass
            self.match(41)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLSQUARE(self, ):

        try:
            _type = LSQUARE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(91)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mRSQUARE(self, ):

        try:
            _type = RSQUARE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(93)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mPLUS(self, ):

        try:
            _type = PLUS
            _channel = DEFAULT_CHANNEL



            pass
            self.match(43)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMINUS(self, ):

        try:
            _type = MINUS
            _channel = DEFAULT_CHANNEL



            pass
            self.match(45)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTIMES(self, ):

        try:
            _type = TIMES
            _channel = DEFAULT_CHANNEL



            pass
            self.match(42)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDIV(self, ):

        try:
            _type = DIV
            _channel = DEFAULT_CHANNEL



            pass
            self.match(47)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLT(self, ):

        try:
            _type = LT
            _channel = DEFAULT_CHANNEL



            pass
            self.match(60)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLE(self, ):

        try:
            _type = LE
            _channel = DEFAULT_CHANNEL



            pass
            self.match("<=")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mGT(self, ):

        try:
            _type = GT
            _channel = DEFAULT_CHANNEL



            pass
            self.match(62)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mGE(self, ):

        try:
            _type = GE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(">=")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mEQ(self, ):

        try:
            _type = EQ
            _channel = DEFAULT_CHANNEL



            pass
            self.match("==")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mNE(self, ):

        try:
            _type = NE
            _channel = DEFAULT_CHANNEL



            pass
            self.match("!=")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mWS(self, ):

        try:
            _type = WS
            _channel = DEFAULT_CHANNEL



            pass

            cnt11 = 0
            while True:
                alt11 = 2
                LA11_0 = self.input.LA(1)

                if ((9 <= LA11_0 <= 10) or LA11_0 == 13 or LA11_0 == 32) :
                    alt11 = 1


                if alt11 == 1:

                    pass
                    if (9 <= self.input.LA(1) <= 10) or self.input.LA(1) == 13 or self.input.LA(1) == 32:
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    if cnt11 >= 1:
                        break

                    eee = EarlyExitException(11, self.input)
                    raise eee

                cnt11 += 1



            self.skip()




            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mEXPONENT(self, ):

        try:


            pass
            if self.input.LA(1) == 69 or self.input.LA(1) == 101:
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse


            alt12 = 2
            LA12_0 = self.input.LA(1)

            if (LA12_0 == 43 or LA12_0 == 45) :
                alt12 = 1
            if alt12 == 1:

                pass
                if self.input.LA(1) == 43 or self.input.LA(1) == 45:
                    self.input.consume()
                else:
                    mse = MismatchedSetException(None, self.input)
                    self.recover(mse)
                    raise mse





            cnt13 = 0
            while True:
                alt13 = 2
                LA13_0 = self.input.LA(1)

                if ((48 <= LA13_0 <= 57)) :
                    alt13 = 1


                if alt13 == 1:

                    pass
                    self.mDIGIT()


                else:
                    if cnt13 >= 1:
                        break

                    eee = EarlyExitException(13, self.input)
                    raise eee

                cnt13 += 1






        finally:

            pass






    def mNAME_START(self, ):

        try:


            pass
            if self.input.LA(1) == 36 or (65 <= self.input.LA(1) <= 90) or self.input.LA(1) == 95 or (97 <= self.input.LA(1) <= 122):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mASCII_LETTER(self, ):

        try:


            pass
            if (65 <= self.input.LA(1) <= 90) or (97 <= self.input.LA(1) <= 122):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mDIGIT(self, ):

        try:


            pass
            self.matchRange(48, 57)




        finally:

            pass






    def mDOLLAR(self, ):

        try:


            pass
            self.match(36)




        finally:

            pass






    def mUNDERSCORE(self, ):

        try:


            pass
            self.match(95)




        finally:

            pass





    def mTokens(self):

        alt14 = 32
        alt14 = self.dfa14.predict(self.input)
        if alt14 == 1:

            pass
            self.mT__32()


        elif alt14 == 2:

            pass
            self.mT__33()


        elif alt14 == 3:

            pass
            self.mT__34()


        elif alt14 == 4:

            pass
            self.mT__35()


        elif alt14 == 5:

            pass
            self.mT__36()


        elif alt14 == 6:

            pass
            self.mT__37()


        elif alt14 == 7:

            pass
            self.mT__38()


        elif alt14 == 8:

            pass
            self.mT__39()


        elif alt14 == 9:

            pass
            self.mT__40()


        elif alt14 == 10:

            pass
            self.mT__41()


        elif alt14 == 11:

            pass
            self.mT__42()


        elif alt14 == 12:

            pass
            self.mT__43()


        elif alt14 == 13:

            pass
            self.mT__44()


        elif alt14 == 14:

            pass
            self.mINT()


        elif alt14 == 15:

            pass
            self.mPHRASE()


        elif alt14 == 16:

            pass
            self.mFLOAT()


        elif alt14 == 17:

            pass
            self.mNAME()


        elif alt14 == 18:

            pass
            self.mLPAREN()


        elif alt14 == 19:

            pass
            self.mRPAREN()


        elif alt14 == 20:

            pass
            self.mLSQUARE()


        elif alt14 == 21:

            pass
            self.mRSQUARE()


        elif alt14 == 22:

            pass
            self.mPLUS()


        elif alt14 == 23:

            pass
            self.mMINUS()


        elif alt14 == 24:

            pass
            self.mTIMES()


        elif alt14 == 25:

            pass
            self.mDIV()


        elif alt14 == 26:

            pass
            self.mLT()


        elif alt14 == 27:

            pass
            self.mLE()


        elif alt14 == 28:

            pass
            self.mGT()


        elif alt14 == 29:

            pass
            self.mGE()


        elif alt14 == 30:

            pass
            self.mEQ()


        elif alt14 == 31:

            pass
            self.mNE()


        elif alt14 == 32:

            pass
            self.mWS()









    DFA9_eot = DFA.unpack(
        u"\5\uffff"
        )

    DFA9_eof = DFA.unpack(
        u"\5\uffff"
        )

    DFA9_min = DFA.unpack(
        u"\2\56\3\uffff"
        )

    DFA9_max = DFA.unpack(
        u"\1\71\1\145\3\uffff"
        )

    DFA9_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1\1\3"
        )

    DFA9_special = DFA.unpack(
        u"\5\uffff"
        )


    DFA9_transition = [
        DFA.unpack(u"\1\2\1\uffff\12\1"),
        DFA.unpack(u"\1\3\1\uffff\12\1\13\uffff\1\4\37\uffff\1\4"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA9 = DFA


    DFA14_eot = DFA.unpack(
        u"\1\uffff\1\33\1\uffff\10\15\1\47\12\uffff\1\51\1\53\5\uffff\2\15"
        u"\1\56\7\15\5\uffff\1\67\1\15\1\uffff\1\15\1\72\1\73\1\74\1\15\1"
        u"\76\1\77\1\15\1\uffff\2\15\3\uffff\1\15\2\uffff\1\15\1\105\1\15"
        u"\1\107\1\15\1\uffff\1\15\1\uffff\2\15\1\114\1\15\1\uffff\1\15\1"
        u"\117\1\uffff"
        )

    DFA14_eof = DFA.unpack(
        u"\120\uffff"
        )

    DFA14_min = DFA.unpack(
        u"\1\11\1\60\1\uffff\1\142\1\157\1\146\1\151\1\145\1\141\1\157\1"
        u"\156\1\56\12\uffff\2\75\5\uffff\1\163\1\165\1\44\1\154\1\156\1"
        u"\147\1\170\1\154\1\167\1\151\5\uffff\1\44\1\156\1\uffff\1\157\3"
        u"\44\1\145\2\44\1\160\1\uffff\1\164\1\155\3\uffff\1\163\2\uffff"
        u"\1\160\1\44\1\145\1\44\1\145\1\uffff\1\164\1\uffff\1\164\1\145"
        u"\1\44\1\162\1\uffff\1\163\1\44\1\uffff"
        )

    DFA14_max = DFA.unpack(
        u"\1\172\1\71\1\uffff\1\142\1\157\1\146\1\151\1\157\1\151\1\157\1"
        u"\156\1\145\12\uffff\2\75\5\uffff\1\163\1\165\1\172\1\154\1\156"
        u"\1\147\1\170\1\156\1\167\1\151\5\uffff\1\172\1\156\1\uffff\1\157"
        u"\3\172\1\145\2\172\1\160\1\uffff\1\164\1\155\3\uffff\1\163\2\uffff"
        u"\1\160\1\172\1\145\1\172\1\145\1\uffff\1\164\1\uffff\1\164\1\145"
        u"\1\172\1\162\1\uffff\1\163\1\172\1\uffff"
        )

    DFA14_accept = DFA.unpack(
        u"\2\uffff\1\2\11\uffff\1\17\1\21\1\22\1\23\1\24\1\25\1\26\1\27\1"
        u"\30\1\31\2\uffff\1\36\1\37\1\40\1\1\1\20\12\uffff\1\16\1\33\1\32"
        u"\1\35\1\34\2\uffff\1\5\10\uffff\1\3\2\uffff\1\7\1\10\1\11\1\uffff"
        u"\1\13\1\14\5\uffff\1\4\1\uffff\1\12\4\uffff\1\15\2\uffff\1\6"
        )

    DFA14_special = DFA.unpack(
        u"\120\uffff"
        )


    DFA14_transition = [
        DFA.unpack(u"\2\32\2\uffff\1\32\22\uffff\1\32\1\31\1\14\1\uffff\1"
        u"\15\3\uffff\1\16\1\17\1\24\1\22\1\2\1\23\1\1\1\25\12\13\2\uffff"
        u"\1\26\1\30\1\27\2\uffff\32\15\1\20\1\uffff\1\21\1\uffff\1\15\1"
        u"\uffff\1\3\1\15\1\4\5\15\1\5\1\15\1\6\1\7\1\10\2\15\1\11\2\15\1"
        u"\12\7\15"),
        DFA.unpack(u"\12\34"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\35"),
        DFA.unpack(u"\1\36"),
        DFA.unpack(u"\1\37"),
        DFA.unpack(u"\1\40"),
        DFA.unpack(u"\1\41\11\uffff\1\42"),
        DFA.unpack(u"\1\43\7\uffff\1\44"),
        DFA.unpack(u"\1\45"),
        DFA.unpack(u"\1\46"),
        DFA.unpack(u"\1\34\1\uffff\12\13\13\uffff\1\34\37\uffff\1\34"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\50"),
        DFA.unpack(u"\1\52"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\54"),
        DFA.unpack(u"\1\55"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\57"),
        DFA.unpack(u"\1\60"),
        DFA.unpack(u"\1\61"),
        DFA.unpack(u"\1\62"),
        DFA.unpack(u"\1\63\1\uffff\1\64"),
        DFA.unpack(u"\1\65"),
        DFA.unpack(u"\1\66"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\70"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\71"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\75"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\100"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\101"),
        DFA.unpack(u"\1\102"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\103"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\104"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\106"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\110"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\111"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\112"),
        DFA.unpack(u"\1\113"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"\1\115"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\116"),
        DFA.unpack(u"\1\15\13\uffff\12\15\7\uffff\32\15\4\uffff\1\15\1\uffff"
        u"\32\15"),
        DFA.unpack(u"")
    ]



    DFA14 = DFA




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import LexerMain
    main = LexerMain(ExpressionLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
