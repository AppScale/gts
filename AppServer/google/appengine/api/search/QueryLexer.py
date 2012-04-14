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


LT=19
EXPONENT=36
LETTER=40
FUZZY=6
OCTAL_ESC=44
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


class QueryLexer(Lexer):

    grammarFileName = "blaze-out/host/genfiles/apphosting/api/search/genantlr/Query.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"

    def __init__(self, input=None, state=None):
        if state is None:
            state = RecognizerSharedState()
        Lexer.__init__(self, input, state)

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







    def mT__45(self, ):

        try:
            _type = T__45
            _channel = DEFAULT_CHANNEL



            pass
            self.match(43)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__46(self, ):

        try:
            _type = T__46
            _channel = DEFAULT_CHANNEL



            pass
            self.match(126)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__47(self, ):

        try:
            _type = T__47
            _channel = DEFAULT_CHANNEL



            pass
            self.match(45)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__48(self, ):

        try:
            _type = T__48
            _channel = DEFAULT_CHANNEL



            pass
            self.match(44)



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






    def mCOLON(self, ):

        try:
            _type = COLON
            _channel = DEFAULT_CHANNEL



            pass
            self.match(58)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFLOAT(self, ):

        try:
            _type = FLOAT
            _channel = DEFAULT_CHANNEL


            alt8 = 3
            alt8 = self.dfa8.predict(self.input)
            if alt8 == 1:

                pass

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


                self.mDOT()

                while True:
                    alt3 = 2
                    LA3_0 = self.input.LA(1)

                    if ((48 <= LA3_0 <= 57)) :
                        alt3 = 1


                    if alt3 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        break



                alt4 = 2
                LA4_0 = self.input.LA(1)

                if (LA4_0 == 69 or LA4_0 == 101) :
                    alt4 = 1
                if alt4 == 1:

                    pass
                    self.mEXPONENT()





            elif alt8 == 2:

                pass
                self.mDOT()

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



                alt6 = 2
                LA6_0 = self.input.LA(1)

                if (LA6_0 == 69 or LA6_0 == 101) :
                    alt6 = 1
                if alt6 == 1:

                    pass
                    self.mEXPONENT()





            elif alt8 == 3:

                pass

                cnt7 = 0
                while True:
                    alt7 = 2
                    LA7_0 = self.input.LA(1)

                    if ((48 <= LA7_0 <= 57)) :
                        alt7 = 1


                    if alt7 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt7 >= 1:
                            break

                        eee = EarlyExitException(7, self.input)
                        raise eee

                    cnt7 += 1


                self.mEXPONENT()


            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mWS(self, ):

        try:
            _type = WS
            _channel = DEFAULT_CHANNEL



            pass
            if (9 <= self.input.LA(1) <= 10) or self.input.LA(1) == 13 or self.input.LA(1) == 32:
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse




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
                alt9 = 3
                LA9_0 = self.input.LA(1)

                if (LA9_0 == 92) :
                    alt9 = 1
                elif ((0 <= LA9_0 <= 33) or (35 <= LA9_0 <= 91) or (93 <= LA9_0 <= 65535)) :
                    alt9 = 2


                if alt9 == 1:

                    pass
                    self.mESC_SEQ()


                elif alt9 == 2:

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






    def mNAME(self, ):

        try:
            _type = NAME
            _channel = DEFAULT_CHANNEL



            pass
            self.mNAME_START()

            while True:
                alt10 = 2
                LA10_0 = self.input.LA(1)

                if ((48 <= LA10_0 <= 57) or (65 <= LA10_0 <= 90) or LA10_0 == 95 or (97 <= LA10_0 <= 122) or (192 <= LA10_0 <= 214) or (216 <= LA10_0 <= 246) or (248 <= LA10_0 <= 8191) or (12352 <= LA10_0 <= 12687) or (13056 <= LA10_0 <= 13183) or (13312 <= LA10_0 <= 15661) or (19968 <= LA10_0 <= 40959) or (63744 <= LA10_0 <= 64255)) :
                    alt10 = 1


                if alt10 == 1:

                    pass
                    self.mNAME_MID()


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






    def mEQ(self, ):

        try:
            _type = EQ
            _channel = DEFAULT_CHANNEL



            pass
            self.match(61)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTEXT(self, ):

        try:
            _type = TEXT
            _channel = DEFAULT_CHANNEL



            pass
            if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or self.input.LA(1) == 44 or (46 <= self.input.LA(1) <= 57) or self.input.LA(1) == 59 or (63 <= self.input.LA(1) <= 125) or (256 <= self.input.LA(1) <= 32767):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse


            while True:
                alt11 = 2
                LA11_0 = self.input.LA(1)

                if (LA11_0 == 33 or (35 <= LA11_0 <= 39) or (44 <= LA11_0 <= 57) or LA11_0 == 59 or (63 <= LA11_0 <= 125) or (256 <= LA11_0 <= 32767)) :
                    alt11 = 1


                if alt11 == 1:

                    pass
                    if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or (44 <= self.input.LA(1) <= 57) or self.input.LA(1) == 59 or (63 <= self.input.LA(1) <= 125) or (256 <= self.input.LA(1) <= 32767):
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






    def mNAME_START(self, ):

        try:


            pass
            if (65 <= self.input.LA(1) <= 90) or self.input.LA(1) == 95 or (97 <= self.input.LA(1) <= 122) or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mNAME_MID(self, ):

        try:


            pass
            if (48 <= self.input.LA(1) <= 57) or (65 <= self.input.LA(1) <= 90) or self.input.LA(1) == 95 or (97 <= self.input.LA(1) <= 122) or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mLETTER(self, ):

        try:


            pass
            if (65 <= self.input.LA(1) <= 90) or (97 <= self.input.LA(1) <= 122) or (192 <= self.input.LA(1) <= 214) or (216 <= self.input.LA(1) <= 246) or (248 <= self.input.LA(1) <= 8191) or (12352 <= self.input.LA(1) <= 12687) or (13056 <= self.input.LA(1) <= 13183) or (13312 <= self.input.LA(1) <= 15661) or (19968 <= self.input.LA(1) <= 40959) or (63744 <= self.input.LA(1) <= 64255):
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






    def mDOT(self, ):

        try:


            pass
            self.match(46)




        finally:

            pass






    def mUNDERSCORE(self, ):

        try:


            pass
            self.match(95)




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
                    self.matchRange(48, 57)


                else:
                    if cnt13 >= 1:
                        break

                    eee = EarlyExitException(13, self.input)
                    raise eee

                cnt13 += 1






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

            alt14 = 3
            LA14_0 = self.input.LA(1)

            if (LA14_0 == 92) :
                LA14 = self.input.LA(2)
                if LA14 == 34 or LA14 == 39 or LA14 == 92 or LA14 == 98 or LA14 == 102 or LA14 == 110 or LA14 == 114 or LA14 == 116:
                    alt14 = 1
                elif LA14 == 117:
                    alt14 = 2
                elif LA14 == 48 or LA14 == 49 or LA14 == 50 or LA14 == 51 or LA14 == 52 or LA14 == 53 or LA14 == 54 or LA14 == 55:
                    alt14 = 3
                else:
                    nvae = NoViableAltException("", 14, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 14, 0, self.input)

                raise nvae

            if alt14 == 1:

                pass
                self.match(92)
                if self.input.LA(1) == 34 or self.input.LA(1) == 39 or self.input.LA(1) == 92 or self.input.LA(1) == 98 or self.input.LA(1) == 102 or self.input.LA(1) == 110 or self.input.LA(1) == 114 or self.input.LA(1) == 116:
                    self.input.consume()
                else:
                    mse = MismatchedSetException(None, self.input)
                    self.recover(mse)
                    raise mse



            elif alt14 == 2:

                pass
                self.mUNICODE_ESC()


            elif alt14 == 3:

                pass
                self.mOCTAL_ESC()



        finally:

            pass






    def mOCTAL_ESC(self, ):

        try:

            alt15 = 3
            LA15_0 = self.input.LA(1)

            if (LA15_0 == 92) :
                LA15_1 = self.input.LA(2)

                if ((48 <= LA15_1 <= 51)) :
                    LA15_2 = self.input.LA(3)

                    if ((48 <= LA15_2 <= 55)) :
                        LA15_4 = self.input.LA(4)

                        if ((48 <= LA15_4 <= 55)) :
                            alt15 = 1
                        else:
                            alt15 = 2
                    else:
                        alt15 = 3
                elif ((52 <= LA15_1 <= 55)) :
                    LA15_3 = self.input.LA(3)

                    if ((48 <= LA15_3 <= 55)) :
                        alt15 = 2
                    else:
                        alt15 = 3
                else:
                    nvae = NoViableAltException("", 15, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 15, 0, self.input)

                raise nvae

            if alt15 == 1:

                pass
                self.match(92)


                pass
                self.matchRange(48, 51)





                pass
                self.matchRange(48, 55)





                pass
                self.matchRange(48, 55)





            elif alt15 == 2:

                pass
                self.match(92)


                pass
                self.matchRange(48, 55)





                pass
                self.matchRange(48, 55)





            elif alt15 == 3:

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

        alt16 = 22
        alt16 = self.dfa16.predict(self.input)
        if alt16 == 1:

            pass
            self.mT__45()


        elif alt16 == 2:

            pass
            self.mT__46()


        elif alt16 == 3:

            pass
            self.mT__47()


        elif alt16 == 4:

            pass
            self.mT__48()


        elif alt16 == 5:

            pass
            self.mOR()


        elif alt16 == 6:

            pass
            self.mAND()


        elif alt16 == 7:

            pass
            self.mNOT()


        elif alt16 == 8:

            pass
            self.mINT()


        elif alt16 == 9:

            pass
            self.mCOLON()


        elif alt16 == 10:

            pass
            self.mFLOAT()


        elif alt16 == 11:

            pass
            self.mWS()


        elif alt16 == 12:

            pass
            self.mPHRASE()


        elif alt16 == 13:

            pass
            self.mNAME()


        elif alt16 == 14:

            pass
            self.mLPAREN()


        elif alt16 == 15:

            pass
            self.mRPAREN()


        elif alt16 == 16:

            pass
            self.mLT()


        elif alt16 == 17:

            pass
            self.mGT()


        elif alt16 == 18:

            pass
            self.mGE()


        elif alt16 == 19:

            pass
            self.mLE()


        elif alt16 == 20:

            pass
            self.mNE()


        elif alt16 == 21:

            pass
            self.mEQ()


        elif alt16 == 22:

            pass
            self.mTEXT()









    DFA8_eot = DFA.unpack(
        u"\5\uffff"
        )

    DFA8_eof = DFA.unpack(
        u"\5\uffff"
        )

    DFA8_min = DFA.unpack(
        u"\2\56\3\uffff"
        )

    DFA8_max = DFA.unpack(
        u"\1\71\1\145\3\uffff"
        )

    DFA8_accept = DFA.unpack(
        u"\2\uffff\1\2\1\1\1\3"
        )

    DFA8_special = DFA.unpack(
        u"\5\uffff"
        )


    DFA8_transition = [
        DFA.unpack(u"\1\2\1\uffff\12\1"),
        DFA.unpack(u"\1\3\1\uffff\12\1\13\uffff\1\4\37\uffff\1\4"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA8 = DFA


    DFA16_eot = DFA.unpack(
        u"\4\uffff\1\26\3\24\1\33\1\uffff\1\25\2\uffff\1\24\2\uffff\1\41"
        u"\1\43\1\25\4\uffff\1\45\3\24\1\uffff\1\33\1\25\2\52\6\uffff\1\56"
        u"\1\57\1\25\1\52\1\uffff\1\52\2\25\2\uffff\1\25\1\52\1\25\1\52"
        )

    DFA16_eof = DFA.unpack(
        u"\64\uffff"
        )

    DFA16_min = DFA.unpack(
        u"\1\11\3\uffff\5\41\1\uffff\1\60\2\uffff\1\41\2\uffff\3\75\4\uffff"
        u"\4\41\1\uffff\1\41\1\53\2\41\6\uffff\2\41\1\60\1\41\1\uffff\1\41"
        u"\2\53\2\uffff\1\60\1\41\1\60\1\41"
        )

    DFA16_max = DFA.unpack(
        u"\1\ufaff\3\uffff\5\u7fff\1\uffff\1\71\2\uffff\1\u7fff\2\uffff\3"
        u"\75\4\uffff\1\ufaff\3\u7fff\1\uffff\1\u7fff\1\71\2\u7fff\6\uffff"
        u"\2\ufaff\1\71\1\u7fff\1\uffff\1\u7fff\2\71\2\uffff\1\71\1\u7fff"
        u"\1\71\1\u7fff"
        )

    DFA16_accept = DFA.unpack(
        u"\1\uffff\1\1\1\2\1\3\5\uffff\1\11\1\uffff\1\13\1\14\1\uffff\1\16"
        u"\1\17\3\uffff\1\25\1\15\1\26\1\4\4\uffff\1\10\4\uffff\1\23\1\20"
        u"\1\22\1\21\1\24\1\5\4\uffff\1\12\3\uffff\1\6\1\7\4\uffff"
        )

    DFA16_special = DFA.unpack(
        u"\64\uffff"
        )


    DFA16_transition = [
        DFA.unpack(u"\2\13\2\uffff\1\13\22\uffff\1\13\1\22\1\14\5\25\1\16"
        u"\1\17\1\uffff\1\1\1\4\1\3\1\12\1\25\12\10\1\11\1\25\1\20\1\23\1"
        u"\21\2\25\1\6\14\15\1\7\1\5\13\15\4\25\1\15\1\25\32\15\3\25\1\2"
        u"\101\uffff\27\24\1\uffff\37\24\1\uffff\10\24\u1f00\15\u1040\25"
        u"\u0150\15\u0170\25\u0080\15\u0080\25\u092e\15\u10d2\25\u3200\15"
        u"\u2000\24\u5900\uffff\u0200\24"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\16\25\1\uffff\1\25\3\uffff"
        u"\77\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\21\30\1\27\10\30\4\25\1\30\1\25\32\30\3\25\u0082"
        u"\uffff\u1f00\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e"
        u"\30\u10d2\25\u3200\30"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\15\30\1\31\14\30\4\25\1\30\1\25\32\30\3\25\u0082"
        u"\uffff\u1f00\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e"
        u"\30\u10d2\25\u3200\30"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\16\30\1\32\13\30\4\25\1\30\1\25\32\30\3\25\u0082"
        u"\uffff\u1f00\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e"
        u"\30\u10d2\25\u3200\30"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\2\25\1\36\1\25\12\34\1\uffff"
        u"\1\25\3\uffff\6\25\1\35\37\25\1\35\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u""),
        DFA.unpack(u"\12\37"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\32\30\4\25\1\30\1\25\32\30\3\25\u0082\uffff\u1f00"
        u"\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e\30\u10d2"
        u"\25\u3200\30"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\40"),
        DFA.unpack(u"\1\42"),
        DFA.unpack(u"\1\44"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\32\30\4\25\1\30\1\25\32\30\3\25\102\uffff\27\24\1"
        u"\uffff\37\24\1\uffff\10\24\u1f00\30\u1040\25\u0150\30\u0170\25"
        u"\u0080\30\u0080\25\u092e\30\u10d2\25\u3200\30\u2000\24\u5900\uffff"
        u"\u0200\24"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\32\30\4\25\1\30\1\25\32\30\3\25\u0082\uffff\u1f00"
        u"\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e\30\u10d2"
        u"\25\u3200\30"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\3\30\1\46\26\30\4\25\1\30\1\25\32\30\3\25\u0082\uffff"
        u"\u1f00\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e\30"
        u"\u10d2\25\u3200\30"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\23\30\1\47\6\30\4\25\1\30\1\25\32\30\3\25\u0082\uffff"
        u"\u1f00\30\u1040\25\u0150\30\u0170\25\u0080\30\u0080\25\u092e\30"
        u"\u10d2\25\u3200\30"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\2\25\1\36\1\25\12\34\1\uffff"
        u"\1\25\3\uffff\6\25\1\35\37\25\1\35\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\52\1\uffff\1\50\2\uffff\12\51"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\53\1\uffff\1\25"
        u"\3\uffff\6\25\1\54\37\25\1\54\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\37\1\uffff\1\25"
        u"\3\uffff\6\25\1\55\37\25\1\55\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\32\30\4\25\1\30\1\25\32\30\3\25\102\uffff\27\24\1"
        u"\uffff\37\24\1\uffff\10\24\u1f00\30\u1040\25\u0150\30\u0170\25"
        u"\u0080\30\u0080\25\u092e\30\u10d2\25\u3200\30\u2000\24\u5900\uffff"
        u"\u0200\24"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\30\1\uffff\1\25"
        u"\3\uffff\2\25\32\30\4\25\1\30\1\25\32\30\3\25\102\uffff\27\24\1"
        u"\uffff\37\24\1\uffff\10\24\u1f00\30\u1040\25\u0150\30\u0170\25"
        u"\u0080\30\u0080\25\u092e\30\u10d2\25\u3200\30\u2000\24\u5900\uffff"
        u"\u0200\24"),
        DFA.unpack(u"\12\51"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\51\1\uffff\1\25"
        u"\3\uffff\77\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\53\1\uffff\1\25"
        u"\3\uffff\6\25\1\54\37\25\1\54\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\52\1\uffff\1\60\2\uffff\12\61"),
        DFA.unpack(u"\1\52\1\uffff\1\62\2\uffff\12\63"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\12\61"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\61\1\uffff\1\25"
        u"\3\uffff\77\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\12\63"),
        DFA.unpack(u"\1\25\1\uffff\5\25\4\uffff\4\25\12\63\1\uffff\1\25"
        u"\3\uffff\77\25\u0082\uffff\u7f00\25")
    ]



    DFA16 = DFA




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import LexerMain
    main = LexerMain(QueryLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
