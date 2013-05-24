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


DOLLAR=49
EXPONENT=44
LT=11
LSQUARE=23
ASCII_LETTER=47
LOG=35
SNIPPET=39
OCTAL_ESC=52
MAX=36
COUNT=31
FLOAT=27
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
NEG=4
OR=8
LEN=34
GT=13
DIV=20
TIMES=19
COND=6
LE=12


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







    def mT__53(self, ):

        try:
            _type = T__53
            _channel = DEFAULT_CHANNEL



            pass
            self.match(46)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mABS(self, ):

        try:
            _type = ABS
            _channel = DEFAULT_CHANNEL



            pass
            self.match("abs")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mCOUNT(self, ):

        try:
            _type = COUNT
            _channel = DEFAULT_CHANNEL



            pass
            self.match("count")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDISTANCE(self, ):

        try:
            _type = DISTANCE
            _channel = DEFAULT_CHANNEL



            pass
            self.match("distance")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mGEOPOINT(self, ):

        try:
            _type = GEOPOINT
            _channel = DEFAULT_CHANNEL



            pass
            self.match("geopoint")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLEN(self, ):

        try:
            _type = LEN
            _channel = DEFAULT_CHANNEL



            pass
            self.match("len")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mLOG(self, ):

        try:
            _type = LOG
            _channel = DEFAULT_CHANNEL



            pass
            self.match("log")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMAX(self, ):

        try:
            _type = MAX
            _channel = DEFAULT_CHANNEL



            pass
            self.match("max")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMIN(self, ):

        try:
            _type = MIN
            _channel = DEFAULT_CHANNEL



            pass
            self.match("min")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mPOW(self, ):

        try:
            _type = POW
            _channel = DEFAULT_CHANNEL



            pass
            self.match("pow")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mAND(self, ):

        try:
            _type = AND
            _channel = DEFAULT_CHANNEL



            pass
            self.match("AND")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mOR(self, ):

        try:
            _type = OR
            _channel = DEFAULT_CHANNEL



            pass
            self.match("OR")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mXOR(self, ):

        try:
            _type = XOR
            _channel = DEFAULT_CHANNEL



            pass
            self.match("XOR")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mNOT(self, ):

        try:
            _type = NOT
            _channel = DEFAULT_CHANNEL



            pass
            self.match("NOT")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSNIPPET(self, ):

        try:
            _type = SNIPPET
            _channel = DEFAULT_CHANNEL



            pass
            self.match("snippet")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSWITCH(self, ):

        try:
            _type = SWITCH
            _channel = DEFAULT_CHANNEL



            pass
            self.match("switch")



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






    def mCOND(self, ):

        try:
            _type = COND
            _channel = DEFAULT_CHANNEL



            pass
            self.match(63)



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






    def mCOMMA(self, ):

        try:
            _type = COMMA
            _channel = DEFAULT_CHANNEL



            pass
            self.match(44)



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

        alt20 = 38
        alt20 = self.dfa20.predict(self.input)
        if alt20 == 1:

            pass
            self.mT__53()


        elif alt20 == 2:

            pass
            self.mABS()


        elif alt20 == 3:

            pass
            self.mCOUNT()


        elif alt20 == 4:

            pass
            self.mDISTANCE()


        elif alt20 == 5:

            pass
            self.mGEOPOINT()


        elif alt20 == 6:

            pass
            self.mLEN()


        elif alt20 == 7:

            pass
            self.mLOG()


        elif alt20 == 8:

            pass
            self.mMAX()


        elif alt20 == 9:

            pass
            self.mMIN()


        elif alt20 == 10:

            pass
            self.mPOW()


        elif alt20 == 11:

            pass
            self.mAND()


        elif alt20 == 12:

            pass
            self.mOR()


        elif alt20 == 13:

            pass
            self.mXOR()


        elif alt20 == 14:

            pass
            self.mNOT()


        elif alt20 == 15:

            pass
            self.mSNIPPET()


        elif alt20 == 16:

            pass
            self.mSWITCH()


        elif alt20 == 17:

            pass
            self.mINT()


        elif alt20 == 18:

            pass
            self.mPHRASE()


        elif alt20 == 19:

            pass
            self.mFLOAT()


        elif alt20 == 20:

            pass
            self.mNAME()


        elif alt20 == 21:

            pass
            self.mLPAREN()


        elif alt20 == 22:

            pass
            self.mRPAREN()


        elif alt20 == 23:

            pass
            self.mLSQUARE()


        elif alt20 == 24:

            pass
            self.mRSQUARE()


        elif alt20 == 25:

            pass
            self.mPLUS()


        elif alt20 == 26:

            pass
            self.mMINUS()


        elif alt20 == 27:

            pass
            self.mTIMES()


        elif alt20 == 28:

            pass
            self.mDIV()


        elif alt20 == 29:

            pass
            self.mLT()


        elif alt20 == 30:

            pass
            self.mLE()


        elif alt20 == 31:

            pass
            self.mGT()


        elif alt20 == 32:

            pass
            self.mGE()


        elif alt20 == 33:

            pass
            self.mEQ()


        elif alt20 == 34:

            pass
            self.mNE()


        elif alt20 == 35:

            pass
            self.mCOND()


        elif alt20 == 36:

            pass
            self.mQUOTE()


        elif alt20 == 37:

            pass
            self.mCOMMA()


        elif alt20 == 38:

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
        u"\3\uffff\1\2\1\1\1\3"
        )

    DFA13_special = DFA.unpack(
        u"\6\uffff"
        )


    DFA13_transition = [
        DFA.unpack(u"\1\1\1\3\1\uffff\12\2"),
        DFA.unpack(u"\1\3\1\uffff\12\2"),
        DFA.unpack(u"\1\4\1\uffff\12\2\13\uffff\1\5\37\uffff\1\5"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA13 = DFA


    DFA20_eot = DFA.unpack(
        u"\1\uffff\1\41\14\21\1\61\1\62\1\63\10\uffff\1\66\1\70\7\uffff\12"
        u"\21\1\103\4\21\10\uffff\1\110\3\21\1\114\1\115\1\116\1\117\1\120"
        u"\1\121\1\uffff\1\122\1\123\2\21\1\uffff\3\21\10\uffff\2\21\1\133"
        u"\4\21\1\uffff\3\21\1\143\2\21\1\146\1\uffff\1\147\1\150\3\uffff"
        )

    DFA20_eof = DFA.unpack(
        u"\151\uffff"
        )

    DFA20_min = DFA.unpack(
        u"\1\11\1\60\1\142\1\157\1\151\2\145\1\141\1\157\1\116\1\122\2\117"
        u"\1\156\2\56\1\0\10\uffff\2\75\7\uffff\1\163\1\165\1\163\1\157\1"
        u"\156\1\147\1\170\1\156\1\167\1\104\1\44\1\122\1\124\2\151\10\uffff"
        u"\1\44\1\156\1\164\1\160\6\44\1\uffff\2\44\1\160\1\164\1\uffff\1"
        u"\164\1\141\1\157\10\uffff\1\160\1\143\1\44\1\156\1\151\1\145\1"
        u"\150\1\uffff\1\143\1\156\1\164\1\44\1\145\1\164\1\44\1\uffff\2"
        u"\44\3\uffff"
        )

    DFA20_max = DFA.unpack(
        u"\1\172\1\71\1\142\1\157\1\151\1\145\1\157\1\151\1\157\1\116\1\122"
        u"\2\117\1\167\1\71\1\145\1\uffff\10\uffff\2\75\7\uffff\1\163\1\165"
        u"\1\163\1\157\1\156\1\147\1\170\1\156\1\167\1\104\1\172\1\122\1"
        u"\124\2\151\10\uffff\1\172\1\156\1\164\1\160\6\172\1\uffff\2\172"
        u"\1\160\1\164\1\uffff\1\164\1\141\1\157\10\uffff\1\160\1\143\1\172"
        u"\1\156\1\151\1\145\1\150\1\uffff\1\143\1\156\1\164\1\172\1\145"
        u"\1\164\1\172\1\uffff\2\172\3\uffff"
        )

    DFA20_accept = DFA.unpack(
        u"\21\uffff\1\24\1\25\1\26\1\27\1\30\1\31\1\33\1\34\2\uffff\1\41"
        u"\1\42\1\43\1\45\1\46\1\23\1\1\17\uffff\1\32\1\21\1\44\1\22\1\36"
        u"\1\35\1\40\1\37\12\uffff\1\14\4\uffff\1\2\3\uffff\1\6\1\7\1\10"
        u"\1\11\1\12\1\13\1\15\1\16\7\uffff\1\3\7\uffff\1\20\2\uffff\1\17"
        u"\1\4\1\5"
        )

    DFA20_special = DFA.unpack(
        u"\20\uffff\1\0\130\uffff"
        )


    DFA20_transition = [
        DFA.unpack(u"\2\37\2\uffff\1\37\22\uffff\1\37\1\34\1\20\1\uffff\1"
        u"\21\3\uffff\1\22\1\23\1\27\1\26\1\36\1\16\1\1\1\30\12\17\2\uffff"
        u"\1\31\1\33\1\32\1\35\1\uffff\1\11\14\21\1\14\1\12\10\21\1\13\2"
        u"\21\1\24\1\uffff\1\25\1\uffff\1\21\1\uffff\1\2\1\21\1\3\1\4\2\21"
        u"\1\5\4\21\1\6\1\7\2\21\1\10\2\21\1\15\7\21"),
        DFA.unpack(u"\12\40"),
        DFA.unpack(u"\1\42"),
        DFA.unpack(u"\1\43"),
        DFA.unpack(u"\1\44"),
        DFA.unpack(u"\1\45"),
        DFA.unpack(u"\1\46\11\uffff\1\47"),
        DFA.unpack(u"\1\50\7\uffff\1\51"),
        DFA.unpack(u"\1\52"),
        DFA.unpack(u"\1\53"),
        DFA.unpack(u"\1\54"),
        DFA.unpack(u"\1\55"),
        DFA.unpack(u"\1\56"),
        DFA.unpack(u"\1\57\10\uffff\1\60"),
        DFA.unpack(u"\1\40\1\uffff\12\17"),
        DFA.unpack(u"\1\40\1\uffff\12\17\13\uffff\1\40\37\uffff\1\40"),
        DFA.unpack(u"\0\64"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\65"),
        DFA.unpack(u"\1\67"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\71"),
        DFA.unpack(u"\1\72"),
        DFA.unpack(u"\1\73"),
        DFA.unpack(u"\1\74"),
        DFA.unpack(u"\1\75"),
        DFA.unpack(u"\1\76"),
        DFA.unpack(u"\1\77"),
        DFA.unpack(u"\1\100"),
        DFA.unpack(u"\1\101"),
        DFA.unpack(u"\1\102"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\104"),
        DFA.unpack(u"\1\105"),
        DFA.unpack(u"\1\106"),
        DFA.unpack(u"\1\107"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\111"),
        DFA.unpack(u"\1\112"),
        DFA.unpack(u"\1\113"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\124"),
        DFA.unpack(u"\1\125"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\126"),
        DFA.unpack(u"\1\127"),
        DFA.unpack(u"\1\130"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\131"),
        DFA.unpack(u"\1\132"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\134"),
        DFA.unpack(u"\1\135"),
        DFA.unpack(u"\1\136"),
        DFA.unpack(u"\1\137"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\140"),
        DFA.unpack(u"\1\141"),
        DFA.unpack(u"\1\142"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\144"),
        DFA.unpack(u"\1\145"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u"\1\21\13\uffff\12\21\7\uffff\32\21\4\uffff\1\21\1\uffff"
        u"\32\21"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    class DFA20(DFA):
        def specialStateTransition(self_, s, input):





            self = self_.recognizer

            _s = s

            if s == 0:
                LA20_16 = input.LA(1)

                s = -1
                if ((0 <= LA20_16 <= 65535)):
                    s = 52

                else:
                    s = 51

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
