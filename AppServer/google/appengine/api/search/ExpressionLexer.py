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


DOLLAR=33
LT=7
EXPONENT=28
LSQUARE=19
ASCII_LETTER=31
OCTAL_ESC=36
FLOAT=23
NAME_START=29
EOF=-1
LPAREN=17
INDEX=5
QUOTE=26
RPAREN=18
NAME=22
ESC_SEQ=27
PLUS=13
DIGIT=25
EQ=11
NE=12
T__42=42
T__43=43
T__40=40
GE=10
T__41=41
T__46=46
T__47=47
T__44=44
T__45=45
T__48=48
T__49=49
UNICODE_ESC=35
HEX_DIGIT=34
UNDERSCORE=32
INT=20
FN=6
MINUS=14
RSQUARE=21
PHRASE=24
WS=30
T__37=37
T__38=38
T__39=39
NEG=4
GT=9
DIV=16
TIMES=15
LE=8


class ExpressionLexer(Lexer):

    grammarFileName = ""
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"

    def __init__(self, input=None, state=None):
        if state is None:
            state = RecognizerSharedState()
        Lexer.__init__(self, input, state)

        self.dfa13 = self.DFA13(
            self, 13,
            eot = self.DFA13_eot,
            eof = self.DFA13_eof,
            min = self.DFA13_min,
            max = self.DFA13_max,
            accept = self.DFA13_accept,
            special = self.DFA13_special,
            transition = self.DFA13_transition
            )

        self.dfa20 = self.DFA20(
            self, 20,
            eot = self.DFA20_eot,
            eof = self.DFA20_eof,
            min = self.DFA20_min,
            max = self.DFA20_max,
            accept = self.DFA20_accept,
            special = self.DFA20_special,
            transition = self.DFA20_transition
            )







    def mT__37(self, ):

        try:
            _type = T__37
            _channel = DEFAULT_CHANNEL



            pass
            self.match(46)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__38(self, ):

        try:
            _type = T__38
            _channel = DEFAULT_CHANNEL



            pass
            self.match(44)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__39(self, ):

        try:
            _type = T__39
            _channel = DEFAULT_CHANNEL



            pass
            self.match("abs")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__40(self, ):

        try:
            _type = T__40
            _channel = DEFAULT_CHANNEL



            pass
            self.match("count")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__41(self, ):

        try:
            _type = T__41
            _channel = DEFAULT_CHANNEL



            pass
            self.match("distance")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__42(self, ):

        try:
            _type = T__42
            _channel = DEFAULT_CHANNEL



            pass
            self.match("geopoint")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__43(self, ):

        try:
            _type = T__43
            _channel = DEFAULT_CHANNEL



            pass
            self.match("if")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__44(self, ):

        try:
            _type = T__44
            _channel = DEFAULT_CHANNEL



            pass
            self.match("len")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__45(self, ):

        try:
            _type = T__45
            _channel = DEFAULT_CHANNEL



            pass
            self.match("log")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__46(self, ):

        try:
            _type = T__46
            _channel = DEFAULT_CHANNEL



            pass
            self.match("max")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__47(self, ):

        try:
            _type = T__47
            _channel = DEFAULT_CHANNEL



            pass
            self.match("min")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__48(self, ):

        try:
            _type = T__48
            _channel = DEFAULT_CHANNEL



            pass
            self.match("pow")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__49(self, ):

        try:
            _type = T__49
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

            alt1 = 2
            LA1_0 = self.input.LA(1)

            if (LA1_0 == 45) :
                alt1 = 1
            if alt1 == 1:

                pass
                self.match(45)




            cnt2 = 0
            while True:
                alt2 = 2
                LA2_0 = self.input.LA(1)

                if ((48 <= LA2_0 <= 57)) :
                    alt2 = 1


                if alt2 == 1:

                    pass
                    self.mDIGIT()


                else:
                    if cnt2 >= 1:
                        break

                    eee = EarlyExitException(2, self.input)
                    raise eee

                cnt2 += 1





            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mPHRASE(self, ):

        try:
            _type = PHRASE
            _channel = DEFAULT_CHANNEL



            pass
            self.mQUOTE()

            while True:
                alt3 = 3
                LA3_0 = self.input.LA(1)

                if (LA3_0 == 92) :
                    alt3 = 1
                elif ((0 <= LA3_0 <= 33) or (35 <= LA3_0 <= 91) or (93 <= LA3_0 <= 65535)) :
                    alt3 = 2


                if alt3 == 1:

                    pass
                    self.mESC_SEQ()


                elif alt3 == 2:

                    pass
                    if (0 <= self.input.LA(1) <= 33) or (35 <= self.input.LA(1) <= 91) or (93 <= self.input.LA(1) <= 65535):
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    break


            self.mQUOTE()



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFLOAT(self, ):

        try:
            _type = FLOAT
            _channel = DEFAULT_CHANNEL


            alt13 = 3
            alt13 = self.dfa13.predict(self.input)
            if alt13 == 1:

                pass

                alt4 = 2
                LA4_0 = self.input.LA(1)

                if (LA4_0 == 45) :
                    alt4 = 1
                if alt4 == 1:

                    pass
                    self.match(45)




                cnt5 = 0
                while True:
                    alt5 = 2
                    LA5_0 = self.input.LA(1)

                    if ((48 <= LA5_0 <= 57)) :
                        alt5 = 1


                    if alt5 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt5 >= 1:
                            break

                        eee = EarlyExitException(5, self.input)
                        raise eee

                    cnt5 += 1


                self.match(46)

                while True:
                    alt6 = 2
                    LA6_0 = self.input.LA(1)

                    if ((48 <= LA6_0 <= 57)) :
                        alt6 = 1


                    if alt6 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        break



                alt7 = 2
                LA7_0 = self.input.LA(1)

                if (LA7_0 == 69 or LA7_0 == 101) :
                    alt7 = 1
                if alt7 == 1:

                    pass
                    self.mEXPONENT()





            elif alt13 == 2:

                pass

                alt8 = 2
                LA8_0 = self.input.LA(1)

                if (LA8_0 == 45) :
                    alt8 = 1
                if alt8 == 1:

                    pass
                    self.match(45)



                self.match(46)

                cnt9 = 0
                while True:
                    alt9 = 2
                    LA9_0 = self.input.LA(1)

                    if ((48 <= LA9_0 <= 57)) :
                        alt9 = 1


                    if alt9 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt9 >= 1:
                            break

                        eee = EarlyExitException(9, self.input)
                        raise eee

                    cnt9 += 1



                alt10 = 2
                LA10_0 = self.input.LA(1)

                if (LA10_0 == 69 or LA10_0 == 101) :
                    alt10 = 1
                if alt10 == 1:

                    pass
                    self.mEXPONENT()





            elif alt13 == 3:

                pass

                alt11 = 2
                LA11_0 = self.input.LA(1)

                if (LA11_0 == 45) :
                    alt11 = 1
                if alt11 == 1:

                    pass
                    self.match(45)




                cnt12 = 0
                while True:
                    alt12 = 2
                    LA12_0 = self.input.LA(1)

                    if ((48 <= LA12_0 <= 57)) :
                        alt12 = 1


                    if alt12 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt12 >= 1:
                            break

                        eee = EarlyExitException(12, self.input)
                        raise eee

                    cnt12 += 1


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
                alt14 = 2
                LA14_0 = self.input.LA(1)

                if (LA14_0 == 36 or (48 <= LA14_0 <= 57) or (65 <= LA14_0 <= 90) or LA14_0 == 95 or (97 <= LA14_0 <= 122)) :
                    alt14 = 1


                if alt14 == 1:

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






    def mQUOTE(self, ):

        try:
            _type = QUOTE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(34)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mWS(self, ):

        try:
            _type = WS
            _channel = DEFAULT_CHANNEL



            pass

            cnt15 = 0
            while True:
                alt15 = 2
                LA15_0 = self.input.LA(1)

                if ((9 <= LA15_0 <= 10) or LA15_0 == 13 or LA15_0 == 32) :
                    alt15 = 1


                if alt15 == 1:

                    pass
                    if (9 <= self.input.LA(1) <= 10) or self.input.LA(1) == 13 or self.input.LA(1) == 32:
                        self.input.consume()
                    else:
                        mse = MismatchedSetException(None, self.input)
                        self.recover(mse)
                        raise mse



                else:
                    if cnt15 >= 1:
                        break

                    eee = EarlyExitException(15, self.input)
                    raise eee

                cnt15 += 1



            _channel = HIDDEN;




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


            alt16 = 2
            LA16_0 = self.input.LA(1)

            if (LA16_0 == 43 or LA16_0 == 45) :
                alt16 = 1
            if alt16 == 1:

                pass
                if self.input.LA(1) == 43 or self.input.LA(1) == 45:
                    self.input.consume()
                else:
                    mse = MismatchedSetException(None, self.input)
                    self.recover(mse)
                    raise mse





            cnt17 = 0
            while True:
                alt17 = 2
                LA17_0 = self.input.LA(1)

                if ((48 <= LA17_0 <= 57)) :
                    alt17 = 1


                if alt17 == 1:

                    pass
                    self.mDIGIT()


                else:
                    if cnt17 >= 1:
                        break

                    eee = EarlyExitException(17, self.input)
                    raise eee

                cnt17 += 1






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






    def mHEX_DIGIT(self, ):

        try:


            pass
            if (48 <= self.input.LA(1) <= 57) or (65 <= self.input.LA(1) <= 70) or (97 <= self.input.LA(1) <= 102):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mESC_SEQ(self, ):

        try:

            alt18 = 3
            LA18_0 = self.input.LA(1)

            if (LA18_0 == 92) :
                LA18 = self.input.LA(2)
                if LA18 == 34 or LA18 == 39 or LA18 == 92 or LA18 == 98 or LA18 == 102 or LA18 == 110 or LA18 == 114 or LA18 == 116:
                    alt18 = 1
                elif LA18 == 117:
                    alt18 = 2
                elif LA18 == 48 or LA18 == 49 or LA18 == 50 or LA18 == 51 or LA18 == 52 or LA18 == 53 or LA18 == 54 or LA18 == 55:
                    alt18 = 3
                else:
                    nvae = NoViableAltException("", 18, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 18, 0, self.input)

                raise nvae

            if alt18 == 1:

                pass
                self.match(92)
                if self.input.LA(1) == 34 or self.input.LA(1) == 39 or self.input.LA(1) == 92 or self.input.LA(1) == 98 or self.input.LA(1) == 102 or self.input.LA(1) == 110 or self.input.LA(1) == 114 or self.input.LA(1) == 116:
                    self.input.consume()
                else:
                    mse = MismatchedSetException(None, self.input)
                    self.recover(mse)
                    raise mse



            elif alt18 == 2:

                pass
                self.mUNICODE_ESC()


            elif alt18 == 3:

                pass
                self.mOCTAL_ESC()



        finally:

            pass






    def mOCTAL_ESC(self, ):

        try:

            alt19 = 3
            LA19_0 = self.input.LA(1)

            if (LA19_0 == 92) :
                LA19_1 = self.input.LA(2)

                if ((48 <= LA19_1 <= 51)) :
                    LA19_2 = self.input.LA(3)

                    if ((48 <= LA19_2 <= 55)) :
                        LA19_4 = self.input.LA(4)

                        if ((48 <= LA19_4 <= 55)) :
                            alt19 = 1
                        else:
                            alt19 = 2
                    else:
                        alt19 = 3
                elif ((52 <= LA19_1 <= 55)) :
                    LA19_3 = self.input.LA(3)

                    if ((48 <= LA19_3 <= 55)) :
                        alt19 = 2
                    else:
                        alt19 = 3
                else:
                    nvae = NoViableAltException("", 19, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 19, 0, self.input)

                raise nvae

            if alt19 == 1:

                pass
                self.match(92)


                pass
                self.matchRange(48, 51)





                pass
                self.matchRange(48, 55)





                pass
                self.matchRange(48, 55)





            elif alt19 == 2:

                pass
                self.match(92)


                pass
                self.matchRange(48, 55)





                pass
                self.matchRange(48, 55)





            elif alt19 == 3:

                pass
                self.match(92)


                pass
                self.matchRange(48, 55)






        finally:

            pass






    def mUNICODE_ESC(self, ):

        try:


            pass
            self.match(92)
            self.match(117)
            self.mHEX_DIGIT()
            self.mHEX_DIGIT()
            self.mHEX_DIGIT()
            self.mHEX_DIGIT()




        finally:

            pass





    def mTokens(self):

        alt20 = 33
        alt20 = self.dfa20.predict(self.input)
        if alt20 == 1:

            pass
            self.mT__37()


        elif alt20 == 2:

            pass
            self.mT__38()


        elif alt20 == 3:

            pass
            self.mT__39()


        elif alt20 == 4:

            pass
            self.mT__40()


        elif alt20 == 5:

            pass
            self.mT__41()


        elif alt20 == 6:

            pass
            self.mT__42()


        elif alt20 == 7:

            pass
            self.mT__43()


        elif alt20 == 8:

            pass
            self.mT__44()


        elif alt20 == 9:

            pass
            self.mT__45()


        elif alt20 == 10:

            pass
            self.mT__46()


        elif alt20 == 11:

            pass
            self.mT__47()


        elif alt20 == 12:

            pass
            self.mT__48()


        elif alt20 == 13:

            pass
            self.mT__49()


        elif alt20 == 14:

            pass
            self.mINT()


        elif alt20 == 15:

            pass
            self.mPHRASE()


        elif alt20 == 16:

            pass
            self.mFLOAT()


        elif alt20 == 17:

            pass
            self.mNAME()


        elif alt20 == 18:

            pass
            self.mLPAREN()


        elif alt20 == 19:

            pass
            self.mRPAREN()


        elif alt20 == 20:

            pass
            self.mLSQUARE()


        elif alt20 == 21:

            pass
            self.mRSQUARE()


        elif alt20 == 22:

            pass
            self.mPLUS()


        elif alt20 == 23:

            pass
            self.mMINUS()


        elif alt20 == 24:

            pass
            self.mTIMES()


        elif alt20 == 25:

            pass
            self.mDIV()


        elif alt20 == 26:

            pass
            self.mLT()


        elif alt20 == 27:

            pass
            self.mLE()


        elif alt20 == 28:

            pass
            self.mGT()


        elif alt20 == 29:

            pass
            self.mGE()


        elif alt20 == 30:

            pass
            self.mEQ()


        elif alt20 == 31:

            pass
            self.mNE()


        elif alt20 == 32:

            pass
            self.mQUOTE()


        elif alt20 == 33:

            pass
            self.mWS()









    DFA13_eot = DFA.unpack(
        u"\6\uffff"
        )

    DFA13_eof = DFA.unpack(
        u"\6\uffff"
        )

    DFA13_min = DFA.unpack(
        u"\1\55\2\56\3\uffff"
        )

    DFA13_max = DFA.unpack(
        u"\2\71\1\145\3\uffff"
        )

    DFA13_accept = DFA.unpack(
        u"\3\uffff\1\2\1\3\1\1"
        )

    DFA13_special = DFA.unpack(
        u"\6\uffff"
        )


    DFA13_transition = [
        DFA.unpack(u"\1\1\1\3\1\uffff\12\2"),
        DFA.unpack(u"\1\3\1\uffff\12\2"),
        DFA.unpack(u"\1\5\1\uffff\12\2\13\uffff\1\4\37\uffff\1\4"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA13 = DFA


    DFA20_eot = DFA.unpack(
        u"\1\uffff\1\35\1\uffff\11\17\1\51\1\52\1\53\10\uffff\1\56\1\60\5"
        u"\uffff\4\17\1\65\6\17\10\uffff\1\74\3\17\1\uffff\1\100\1\101\1"
        u"\102\1\103\1\104\1\17\1\uffff\3\17\5\uffff\1\17\1\112\3\17\1\uffff"
        u"\5\17\1\123\1\124\1\125\3\uffff"
        )

    DFA20_eof = DFA.unpack(
        u"\126\uffff"
        )

    DFA20_min = DFA.unpack(
        u"\1\11\1\60\1\uffff\1\142\1\157\1\151\1\145\1\146\1\145\1\141\1"
        u"\157\1\156\2\56\1\0\10\uffff\2\75\5\uffff\1\163\1\165\1\163\1\157"
        u"\1\44\1\156\1\147\1\170\1\156\1\167\1\151\10\uffff\1\44\1\156\1"
        u"\164\1\160\1\uffff\5\44\1\160\1\uffff\1\164\1\141\1\157\5\uffff"
        u"\1\160\1\44\1\156\1\151\1\145\1\uffff\1\143\1\156\1\164\1\145\1"
        u"\164\3\44\3\uffff"
        )

    DFA20_max = DFA.unpack(
        u"\1\172\1\71\1\uffff\1\142\1\157\1\151\1\145\1\146\1\157\1\151\1"
        u"\157\1\156\1\71\1\145\1\uffff\10\uffff\2\75\5\uffff\1\163\1\165"
        u"\1\163\1\157\1\172\1\156\1\147\1\170\1\156\1\167\1\151\10\uffff"
        u"\1\172\1\156\1\164\1\160\1\uffff\5\172\1\160\1\uffff\1\164\1\141"
        u"\1\157\5\uffff\1\160\1\172\1\156\1\151\1\145\1\uffff\1\143\1\156"
        u"\1\164\1\145\1\164\3\172\3\uffff"
        )

    DFA20_accept = DFA.unpack(
        u"\2\uffff\1\2\14\uffff\1\21\1\22\1\23\1\24\1\25\1\26\1\30\1\31\2"
        u"\uffff\1\36\1\37\1\41\1\20\1\1\13\uffff\1\27\1\16\1\40\1\17\1\33"
        u"\1\32\1\35\1\34\4\uffff\1\7\6\uffff\1\3\3\uffff\1\10\1\11\1\12"
        u"\1\13\1\14\5\uffff\1\4\10\uffff\1\15\1\5\1\6"
        )

    DFA20_special = DFA.unpack(
        u"\16\uffff\1\0\107\uffff"
        )


    DFA20_transition = [
        DFA.unpack(u"\2\33\2\uffff\1\33\22\uffff\1\33\1\32\1\16\1\uffff\1"
        u"\17\3\uffff\1\20\1\21\1\25\1\24\1\2\1\14\1\1\1\26\12\15\2\uffff"
        u"\1\27\1\31\1\30\2\uffff\32\17\1\22\1\uffff\1\23\1\uffff\1\17\1"
        u"\uffff\1\3\1\17\1\4\1\5\2\17\1\6\1\17\1\7\2\17\1\10\1\11\2\17\1"
        u"\12\2\17\1\13\7\17"),
        DFA.unpack(u"\12\34"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\36"),
        DFA.unpack(u"\1\37"),
        DFA.unpack(u"\1\40"),
        DFA.unpack(u"\1\41"),
        DFA.unpack(u"\1\42"),
        DFA.unpack(u"\1\43\11\uffff\1\44"),
        DFA.unpack(u"\1\45\7\uffff\1\46"),
        DFA.unpack(u"\1\47"),
        DFA.unpack(u"\1\50"),
        DFA.unpack(u"\1\34\1\uffff\12\15"),
        DFA.unpack(u"\1\34\1\uffff\12\15\13\uffff\1\34\37\uffff\1\34"),
        DFA.unpack(u"\0\54"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\55"),
        DFA.unpack(u"\1\57"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\61"),
        DFA.unpack(u"\1\62"),
        DFA.unpack(u"\1\63"),
        DFA.unpack(u"\1\64"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\66"),
        DFA.unpack(u"\1\67"),
        DFA.unpack(u"\1\70"),
        DFA.unpack(u"\1\71"),
        DFA.unpack(u"\1\72"),
        DFA.unpack(u"\1\73"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\75"),
        DFA.unpack(u"\1\76"),
        DFA.unpack(u"\1\77"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\105"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\106"),
        DFA.unpack(u"\1\107"),
        DFA.unpack(u"\1\110"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\111"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\113"),
        DFA.unpack(u"\1\114"),
        DFA.unpack(u"\1\115"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\116"),
        DFA.unpack(u"\1\117"),
        DFA.unpack(u"\1\120"),
        DFA.unpack(u"\1\121"),
        DFA.unpack(u"\1\122"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u"\1\17\13\uffff\12\17\7\uffff\32\17\4\uffff\1\17\1\uffff"
        u"\32\17"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    class DFA20(DFA):
        def specialStateTransition(self_, s, input):





            self = self_.recognizer

            _s = s

            if s == 0:
                LA20_14 = input.LA(1)

                s = -1
                if ((0 <= LA20_14 <= 65535)):
                    s = 44

                else:
                    s = 43

                if s >= 0:
                    return s

            nvae = NoViableAltException(self_.getDescription(), 20, _s, input)
            self_.error(nvae)
            raise nvae




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import LexerMain
    main = LexerMain(ExpressionLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
