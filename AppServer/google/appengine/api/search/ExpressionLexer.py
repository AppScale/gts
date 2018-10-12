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


DOLLAR=54
EXPONENT=49
LT=11
LSQUARE=23
ASCII_LETTER=52
LOG=40
SNIPPET=44
OCTAL_ESC=57
MAX=41
COUNT=37
FLOAT=33
NAME_START=50
HTML=28
NOT=10
ATOM=29
AND=7
EOF=-1
LPAREN=21
INDEX=5
QUOTE=47
RPAREN=22
DISTANCE=38
T__58=58
NAME=26
ESC_SEQ=48
POW=43
COMMA=35
PLUS=17
GEO=32
DIGIT=46
EQ=15
NE=16
GE=14
XOR=9
SWITCH=45
UNICODE_ESC=56
NUMBER=31
HEX_DIGIT=55
UNDERSCORE=53
INT=24
MIN=42
TEXT=27
RSQUARE=25
MINUS=18
GEOPOINT=39
PHRASE=34
ABS=36
WS=51
NEG=4
OR=8
GT=13
DIV=20
DATE=30
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







    def mT__58(self, ):

        try:
            _type = T__58
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






    def mTEXT(self, ):

        try:
            _type = TEXT
            _channel = DEFAULT_CHANNEL



            pass
            self.match("text")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mHTML(self, ):

        try:
            _type = HTML
            _channel = DEFAULT_CHANNEL



            pass
            self.match("html")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mATOM(self, ):

        try:
            _type = ATOM
            _channel = DEFAULT_CHANNEL



            pass
            self.match("atom")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDATE(self, ):

        try:
            _type = DATE
            _channel = DEFAULT_CHANNEL



            pass
            self.match("date")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mNUMBER(self, ):

        try:
            _type = NUMBER
            _channel = DEFAULT_CHANNEL



            pass
            self.match("number")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mGEO(self, ):

        try:
            _type = GEO
            _channel = DEFAULT_CHANNEL



            pass
            self.match("geo")



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

        alt20 = 43
        alt20 = self.dfa20.predict(self.input)
        if alt20 == 1:

            pass
            self.mT__58()


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
            self.mLOG()


        elif alt20 == 7:

            pass
            self.mMAX()


        elif alt20 == 8:

            pass
            self.mMIN()


        elif alt20 == 9:

            pass
            self.mPOW()


        elif alt20 == 10:

            pass
            self.mAND()


        elif alt20 == 11:

            pass
            self.mOR()


        elif alt20 == 12:

            pass
            self.mXOR()


        elif alt20 == 13:

            pass
            self.mNOT()


        elif alt20 == 14:

            pass
            self.mSNIPPET()


        elif alt20 == 15:

            pass
            self.mSWITCH()


        elif alt20 == 16:

            pass
            self.mTEXT()


        elif alt20 == 17:

            pass
            self.mHTML()


        elif alt20 == 18:

            pass
            self.mATOM()


        elif alt20 == 19:

            pass
            self.mDATE()


        elif alt20 == 20:

            pass
            self.mNUMBER()


        elif alt20 == 21:

            pass
            self.mGEO()


        elif alt20 == 22:

            pass
            self.mINT()


        elif alt20 == 23:

            pass
            self.mPHRASE()


        elif alt20 == 24:

            pass
            self.mFLOAT()


        elif alt20 == 25:

            pass
            self.mNAME()


        elif alt20 == 26:

            pass
            self.mLPAREN()


        elif alt20 == 27:

            pass
            self.mRPAREN()


        elif alt20 == 28:

            pass
            self.mLSQUARE()


        elif alt20 == 29:

            pass
            self.mRSQUARE()


        elif alt20 == 30:

            pass
            self.mPLUS()


        elif alt20 == 31:

            pass
            self.mMINUS()


        elif alt20 == 32:

            pass
            self.mTIMES()


        elif alt20 == 33:

            pass
            self.mDIV()


        elif alt20 == 34:

            pass
            self.mLT()


        elif alt20 == 35:

            pass
            self.mLE()


        elif alt20 == 36:

            pass
            self.mGT()


        elif alt20 == 37:

            pass
            self.mGE()


        elif alt20 == 38:

            pass
            self.mEQ()


        elif alt20 == 39:

            pass
            self.mNE()


        elif alt20 == 40:

            pass
            self.mCOND()


        elif alt20 == 41:

            pass
            self.mQUOTE()


        elif alt20 == 42:

            pass
            self.mCOMMA()


        elif alt20 == 43:

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
        u"\1\uffff\1\44\17\24\1\70\1\71\1\72\10\uffff\1\75\1\77\7\uffff\13"
        u"\24\1\113\7\24\10\uffff\1\123\4\24\1\131\1\132\1\133\1\134\1\135"
        u"\1\136\1\uffff\1\137\1\140\5\24\1\uffff\1\146\2\24\1\151\1\24\10"
        u"\uffff\2\24\1\155\1\156\1\24\1\uffff\1\160\1\24\1\uffff\3\24\2"
        u"\uffff\1\24\1\uffff\3\24\1\171\1\172\2\24\1\175\2\uffff\1\176\1"
        u"\177\3\uffff"
        )

    DFA20_eof = DFA.unpack(
        u"\u0080\uffff"
        )

    DFA20_min = DFA.unpack(
        u"\1\11\1\60\1\142\1\157\1\141\1\145\1\157\1\141\1\157\1\116\1\122"
        u"\2\117\1\156\1\145\1\164\1\165\2\56\1\0\10\uffff\2\75\7\uffff\1"
        u"\163\1\157\1\165\1\163\1\164\1\157\1\147\1\170\1\156\1\167\1\104"
        u"\1\44\1\122\1\124\2\151\1\170\2\155\10\uffff\1\44\1\155\1\156\1"
        u"\164\1\145\6\44\1\uffff\2\44\1\160\2\164\1\154\1\142\1\uffff\1"
        u"\44\1\164\1\141\1\44\1\157\10\uffff\1\160\1\143\2\44\1\145\1\uffff"
        u"\1\44\1\156\1\uffff\1\151\1\145\1\150\2\uffff\1\162\1\uffff\1\143"
        u"\1\156\1\164\2\44\1\145\1\164\1\44\2\uffff\2\44\3\uffff"
        )

    DFA20_max = DFA.unpack(
        u"\1\172\1\71\1\164\1\157\1\151\1\145\1\157\1\151\1\157\1\116\1\122"
        u"\2\117\1\167\1\145\1\164\1\165\1\71\1\145\1\uffff\10\uffff\2\75"
        u"\7\uffff\1\163\1\157\1\165\1\163\1\164\1\157\1\147\1\170\1\156"
        u"\1\167\1\104\1\172\1\122\1\124\2\151\1\170\2\155\10\uffff\1\172"
        u"\1\155\1\156\1\164\1\145\6\172\1\uffff\2\172\1\160\2\164\1\154"
        u"\1\142\1\uffff\1\172\1\164\1\141\1\172\1\157\10\uffff\1\160\1\143"
        u"\2\172\1\145\1\uffff\1\172\1\156\1\uffff\1\151\1\145\1\150\2\uffff"
        u"\1\162\1\uffff\1\143\1\156\1\164\2\172\1\145\1\164\1\172\2\uffff"
        u"\2\172\3\uffff"
        )

    DFA20_accept = DFA.unpack(
        u"\24\uffff\1\31\1\32\1\33\1\34\1\35\1\36\1\40\1\41\2\uffff\1\46"
        u"\1\47\1\50\1\52\1\53\1\30\1\1\23\uffff\1\37\1\26\1\51\1\27\1\43"
        u"\1\42\1\45\1\44\13\uffff\1\13\7\uffff\1\2\5\uffff\1\25\1\6\1\7"
        u"\1\10\1\11\1\12\1\14\1\15\5\uffff\1\22\2\uffff\1\23\3\uffff\1\20"
        u"\1\21\1\uffff\1\3\10\uffff\1\17\1\24\2\uffff\1\16\1\4\1\5"
        )

    DFA20_special = DFA.unpack(
        u"\23\uffff\1\0\154\uffff"
        )


    DFA20_transition = [
        DFA.unpack(u"\2\42\2\uffff\1\42\22\uffff\1\42\1\37\1\23\1\uffff\1"
        u"\24\3\uffff\1\25\1\26\1\32\1\31\1\41\1\21\1\1\1\33\12\22\2\uffff"
        u"\1\34\1\36\1\35\1\40\1\uffff\1\11\14\24\1\14\1\12\10\24\1\13\2"
        u"\24\1\27\1\uffff\1\30\1\uffff\1\24\1\uffff\1\2\1\24\1\3\1\4\2\24"
        u"\1\5\1\17\3\24\1\6\1\7\1\20\1\24\1\10\2\24\1\15\1\16\6\24"),
        DFA.unpack(u"\12\43"),
        DFA.unpack(u"\1\45\21\uffff\1\46"),
        DFA.unpack(u"\1\47"),
        DFA.unpack(u"\1\51\7\uffff\1\50"),
        DFA.unpack(u"\1\52"),
        DFA.unpack(u"\1\53"),
        DFA.unpack(u"\1\54\7\uffff\1\55"),
        DFA.unpack(u"\1\56"),
        DFA.unpack(u"\1\57"),
        DFA.unpack(u"\1\60"),
        DFA.unpack(u"\1\61"),
        DFA.unpack(u"\1\62"),
        DFA.unpack(u"\1\63\10\uffff\1\64"),
        DFA.unpack(u"\1\65"),
        DFA.unpack(u"\1\66"),
        DFA.unpack(u"\1\67"),
        DFA.unpack(u"\1\43\1\uffff\12\22"),
        DFA.unpack(u"\1\43\1\uffff\12\22\13\uffff\1\43\37\uffff\1\43"),
        DFA.unpack(u"\0\73"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\74"),
        DFA.unpack(u"\1\76"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\100"),
        DFA.unpack(u"\1\101"),
        DFA.unpack(u"\1\102"),
        DFA.unpack(u"\1\103"),
        DFA.unpack(u"\1\104"),
        DFA.unpack(u"\1\105"),
        DFA.unpack(u"\1\106"),
        DFA.unpack(u"\1\107"),
        DFA.unpack(u"\1\110"),
        DFA.unpack(u"\1\111"),
        DFA.unpack(u"\1\112"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\114"),
        DFA.unpack(u"\1\115"),
        DFA.unpack(u"\1\116"),
        DFA.unpack(u"\1\117"),
        DFA.unpack(u"\1\120"),
        DFA.unpack(u"\1\121"),
        DFA.unpack(u"\1\122"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\124"),
        DFA.unpack(u"\1\125"),
        DFA.unpack(u"\1\126"),
        DFA.unpack(u"\1\127"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\17\24\1\130\12\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\141"),
        DFA.unpack(u"\1\142"),
        DFA.unpack(u"\1\143"),
        DFA.unpack(u"\1\144"),
        DFA.unpack(u"\1\145"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\147"),
        DFA.unpack(u"\1\150"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\152"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\153"),
        DFA.unpack(u"\1\154"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\157"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\161"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\162"),
        DFA.unpack(u"\1\163"),
        DFA.unpack(u"\1\164"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\165"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\166"),
        DFA.unpack(u"\1\167"),
        DFA.unpack(u"\1\170"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\173"),
        DFA.unpack(u"\1\174"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u"\1\24\13\uffff\12\24\7\uffff\32\24\4\uffff\1\24\1\uffff"
        u"\32\24"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    class DFA20(DFA):
        def specialStateTransition(self_, s, input):





            self = self_.recognizer

            _s = s

            if s == 0:
                LA20_19 = input.LA(1)

                s = -1
                if ((0 <= LA20_19 <= 65535)):
                    s = 59

                else:
                    s = 58

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
