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


FUNCTION=7
LT=19
EXPONENT=37
LETTER=42
FUZZY=8
OCTAL_ESC=46
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
OR=33
NEG=41
GT=21
GLOBAL=11
LE=18
STRING=14


class QueryLexer(Lexer):

    grammarFileName = ""
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"

    def __init__(self, input=None, state=None):
        if state is None:
            state = RecognizerSharedState()
        Lexer.__init__(self, input, state)

        self.dfa12 = self.DFA12(
            self, 12,
            eot = self.DFA12_eot,
            eof = self.DFA12_eof,
            min = self.DFA12_min,
            max = self.DFA12_max,
            accept = self.DFA12_accept,
            special = self.DFA12_special,
            transition = self.DFA12_transition
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







    def mT__47(self, ):

        try:
            _type = T__47
            _channel = DEFAULT_CHANNEL



            pass
            self.match(43)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__48(self, ):

        try:
            _type = T__48
            _channel = DEFAULT_CHANNEL



            pass
            self.match(126)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__49(self, ):

        try:
            _type = T__49
            _channel = DEFAULT_CHANNEL



            pass
            self.match(44)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mHAS(self, ):

        try:
            _type = HAS
            _channel = DEFAULT_CHANNEL



            pass
            self.match(58)



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






    def mFLOAT(self, ):

        try:
            _type = FLOAT
            _channel = DEFAULT_CHANNEL


            alt12 = 3
            alt12 = self.dfa12.predict(self.input)
            if alt12 == 1:

                pass

                alt3 = 2
                LA3_0 = self.input.LA(1)

                if (LA3_0 == 45) :
                    alt3 = 1
                if alt3 == 1:

                    pass
                    self.match(45)




                cnt4 = 0
                while True:
                    alt4 = 2
                    LA4_0 = self.input.LA(1)

                    if ((48 <= LA4_0 <= 57)) :
                        alt4 = 1


                    if alt4 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt4 >= 1:
                            break

                        eee = EarlyExitException(4, self.input)
                        raise eee

                    cnt4 += 1


                self.mDOT()

                while True:
                    alt5 = 2
                    LA5_0 = self.input.LA(1)

                    if ((48 <= LA5_0 <= 57)) :
                        alt5 = 1


                    if alt5 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        break



                alt6 = 2
                LA6_0 = self.input.LA(1)

                if (LA6_0 == 69 or LA6_0 == 101) :
                    alt6 = 1
                if alt6 == 1:

                    pass
                    self.mEXPONENT()





            elif alt12 == 2:

                pass

                alt7 = 2
                LA7_0 = self.input.LA(1)

                if (LA7_0 == 45) :
                    alt7 = 1
                if alt7 == 1:

                    pass
                    self.match(45)



                self.mDOT()

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



                alt9 = 2
                LA9_0 = self.input.LA(1)

                if (LA9_0 == 69 or LA9_0 == 101) :
                    alt9 = 1
                if alt9 == 1:

                    pass
                    self.mEXPONENT()





            elif alt12 == 3:

                pass

                alt10 = 2
                LA10_0 = self.input.LA(1)

                if (LA10_0 == 45) :
                    alt10 = 1
                if alt10 == 1:

                    pass
                    self.match(45)




                cnt11 = 0
                while True:
                    alt11 = 2
                    LA11_0 = self.input.LA(1)

                    if ((48 <= LA11_0 <= 57)) :
                        alt11 = 1


                    if alt11 == 1:

                        pass
                        self.mDIGIT()


                    else:
                        if cnt11 >= 1:
                            break

                        eee = EarlyExitException(11, self.input)
                        raise eee

                    cnt11 += 1


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
                alt13 = 3
                LA13_0 = self.input.LA(1)

                if (LA13_0 == 92) :
                    alt13 = 1
                elif ((0 <= LA13_0 <= 33) or (35 <= LA13_0 <= 91) or (93 <= LA13_0 <= 65535)) :
                    alt13 = 2


                if alt13 == 1:

                    pass
                    self.mESC_SEQ()


                elif alt13 == 2:

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
                alt14 = 2
                LA14_0 = self.input.LA(1)

                if ((48 <= LA14_0 <= 57) or (65 <= LA14_0 <= 90) or LA14_0 == 95 or (97 <= LA14_0 <= 122) or (192 <= LA14_0 <= 214) or (216 <= LA14_0 <= 246) or (248 <= LA14_0 <= 8191) or (12352 <= LA14_0 <= 12687) or (13056 <= LA14_0 <= 13183) or (13312 <= LA14_0 <= 15661) or (19968 <= LA14_0 <= 40959) or (63744 <= LA14_0 <= 64255)) :
                    alt14 = 1


                if alt14 == 1:

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






    def mNEG(self, ):

        try:
            _type = NEG
            _channel = DEFAULT_CHANNEL



            pass
            self.match(45)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTEXT(self, ):

        try:
            _type = TEXT
            _channel = DEFAULT_CHANNEL



            pass
            if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or (46 <= self.input.LA(1) <= 57) or self.input.LA(1) == 59 or (63 <= self.input.LA(1) <= 125) or (256 <= self.input.LA(1) <= 32767):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse


            while True:
                alt15 = 2
                LA15_0 = self.input.LA(1)

                if (LA15_0 == 33 or (35 <= LA15_0 <= 39) or (45 <= LA15_0 <= 57) or LA15_0 == 59 or (63 <= LA15_0 <= 125) or (256 <= LA15_0 <= 32767)) :
                    alt15 = 1


                if alt15 == 1:

                    pass
                    if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or (45 <= self.input.LA(1) <= 57) or self.input.LA(1) == 59 or (63 <= self.input.LA(1) <= 125) or (256 <= self.input.LA(1) <= 32767):
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
                    self.matchRange(48, 57)


                else:
                    if cnt17 >= 1:
                        break

                    eee = EarlyExitException(17, self.input)
                    raise eee

                cnt17 += 1






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

        alt20 = 22
        alt20 = self.dfa20.predict(self.input)
        if alt20 == 1:

            pass
            self.mT__47()


        elif alt20 == 2:

            pass
            self.mT__48()


        elif alt20 == 3:

            pass
            self.mT__49()


        elif alt20 == 4:

            pass
            self.mHAS()


        elif alt20 == 5:

            pass
            self.mOR()


        elif alt20 == 6:

            pass
            self.mAND()


        elif alt20 == 7:

            pass
            self.mNOT()


        elif alt20 == 8:

            pass
            self.mINT()


        elif alt20 == 9:

            pass
            self.mFLOAT()


        elif alt20 == 10:

            pass
            self.mWS()


        elif alt20 == 11:

            pass
            self.mPHRASE()


        elif alt20 == 12:

            pass
            self.mNAME()


        elif alt20 == 13:

            pass
            self.mLPAREN()


        elif alt20 == 14:

            pass
            self.mRPAREN()


        elif alt20 == 15:

            pass
            self.mLT()


        elif alt20 == 16:

            pass
            self.mGT()


        elif alt20 == 17:

            pass
            self.mGE()


        elif alt20 == 18:

            pass
            self.mLE()


        elif alt20 == 19:

            pass
            self.mNE()


        elif alt20 == 20:

            pass
            self.mEQ()


        elif alt20 == 21:

            pass
            self.mNEG()


        elif alt20 == 22:

            pass
            self.mTEXT()









    DFA12_eot = DFA.unpack(
        u"\6\uffff"
        )

    DFA12_eof = DFA.unpack(
        u"\6\uffff"
        )

    DFA12_min = DFA.unpack(
        u"\1\55\2\56\3\uffff"
        )

    DFA12_max = DFA.unpack(
        u"\2\71\1\145\3\uffff"
        )

    DFA12_accept = DFA.unpack(
        u"\3\uffff\1\2\1\3\1\1"
        )

    DFA12_special = DFA.unpack(
        u"\6\uffff"
        )


    DFA12_transition = [
        DFA.unpack(u"\1\1\1\3\1\uffff\12\2"),
        DFA.unpack(u"\1\3\1\uffff\12\2"),
        DFA.unpack(u"\1\5\1\uffff\12\2\13\uffff\1\4\37\uffff\1\4"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA12 = DFA


    DFA20_eot = DFA.unpack(
        u"\5\uffff\3\24\1\32\1\35\1\25\2\uffff\1\24\2\uffff\1\43\1\45\1\25"
        u"\3\uffff\1\47\3\24\1\uffff\1\35\2\uffff\1\25\1\35\2\34\6\uffff"
        u"\1\57\1\60\1\25\2\34\2\25\2\uffff\1\25\1\34\1\25\1\34"
        )

    DFA20_eof = DFA.unpack(
        u"\65\uffff"
        )

    DFA20_min = DFA.unpack(
        u"\1\11\4\uffff\3\41\1\56\1\41\1\60\2\uffff\1\41\2\uffff\3\75\3\uffff"
        u"\4\41\1\uffff\1\56\2\uffff\1\53\3\41\6\uffff\2\41\1\60\2\41\2\53"
        u"\2\uffff\1\60\1\41\1\60\1\41"
        )

    DFA20_max = DFA.unpack(
        u"\1\ufaff\4\uffff\3\u7fff\1\71\1\u7fff\1\71\2\uffff\1\u7fff\2\uffff"
        u"\3\75\3\uffff\1\ufaff\3\u7fff\1\uffff\1\145\2\uffff\1\71\3\u7fff"
        u"\6\uffff\2\ufaff\1\71\2\u7fff\2\71\2\uffff\1\71\1\u7fff\1\71\1"
        u"\u7fff"
        )

    DFA20_accept = DFA.unpack(
        u"\1\uffff\1\1\1\2\1\3\1\4\6\uffff\1\12\1\13\1\uffff\1\15\1\16\3"
        u"\uffff\1\24\1\14\1\26\4\uffff\1\25\1\uffff\1\11\1\10\4\uffff\1"
        u"\22\1\17\1\21\1\20\1\23\1\5\7\uffff\1\6\1\7\4\uffff"
        )

    DFA20_special = DFA.unpack(
        u"\65\uffff"
        )


    DFA20_transition = [
        DFA.unpack(u"\2\13\2\uffff\1\13\22\uffff\1\13\1\22\1\14\5\25\1\16"
        u"\1\17\1\uffff\1\1\1\3\1\10\1\12\1\25\12\11\1\4\1\25\1\20\1\23\1"
        u"\21\2\25\1\6\14\15\1\7\1\5\13\15\4\25\1\15\1\25\32\15\3\25\1\2"
        u"\101\uffff\27\24\1\uffff\37\24\1\uffff\10\24\u1f00\15\u1040\25"
        u"\u0150\15\u0170\25\u0080\15\u0080\25\u092e\15\u10d2\25\u3200\15"
        u"\u2000\24\u5900\uffff\u0200\24"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\21\27\1\26\10\27\4\25\1\27\1\25\32\27\3\25\u0082"
        u"\uffff\u1f00\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e"
        u"\27\u10d2\25\u3200\27"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\15\27\1\30\14\27\4\25\1\27\1\25\32\27\3\25\u0082"
        u"\uffff\u1f00\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e"
        u"\27\u10d2\25\u3200\27"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\16\27\1\31\13\27\4\25\1\27\1\25\32\27\3\25\u0082"
        u"\uffff\u1f00\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e"
        u"\27\u10d2\25\u3200\27"),
        DFA.unpack(u"\1\34\1\uffff\12\33"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\1\25\1\40\1\25\12\37\1\uffff"
        u"\1\25\3\uffff\6\25\1\36\37\25\1\36\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\12\41"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\32\27\4\25\1\27\1\25\32\27\3\25\u0082\uffff\u1f00"
        u"\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e\27\u10d2"
        u"\25\u3200\27"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\42"),
        DFA.unpack(u"\1\44"),
        DFA.unpack(u"\1\46"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\32\27\4\25\1\27\1\25\32\27\3\25\102\uffff\27\24\1"
        u"\uffff\37\24\1\uffff\10\24\u1f00\27\u1040\25\u0150\27\u0170\25"
        u"\u0080\27\u0080\25\u092e\27\u10d2\25\u3200\27\u2000\24\u5900\uffff"
        u"\u0200\24"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\32\27\4\25\1\27\1\25\32\27\3\25\u0082\uffff\u1f00"
        u"\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e\27\u10d2"
        u"\25\u3200\27"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\3\27\1\50\26\27\4\25\1\27\1\25\32\27\3\25\u0082\uffff"
        u"\u1f00\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e\27"
        u"\u10d2\25\u3200\27"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\23\27\1\51\6\27\4\25\1\27\1\25\32\27\3\25\u0082\uffff"
        u"\u1f00\27\u1040\25\u0150\27\u0170\25\u0080\27\u0080\25\u092e\27"
        u"\u10d2\25\u3200\27"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\34\1\uffff\12\33\13\uffff\1\34\37\uffff\1\34"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\34\1\uffff\1\52\2\uffff\12\53"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\1\25\1\40\1\25\12\37\1\uffff"
        u"\1\25\3\uffff\6\25\1\36\37\25\1\36\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\54\1\uffff\1\25"
        u"\3\uffff\6\25\1\55\37\25\1\55\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\41\1\uffff\1\25"
        u"\3\uffff\6\25\1\56\37\25\1\56\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\32\27\4\25\1\27\1\25\32\27\3\25\102\uffff\27\24\1"
        u"\uffff\37\24\1\uffff\10\24\u1f00\27\u1040\25\u0150\27\u0170\25"
        u"\u0080\27\u0080\25\u092e\27\u10d2\25\u3200\27\u2000\24\u5900\uffff"
        u"\u0200\24"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\27\1\uffff\1\25"
        u"\3\uffff\2\25\32\27\4\25\1\27\1\25\32\27\3\25\102\uffff\27\24\1"
        u"\uffff\37\24\1\uffff\10\24\u1f00\27\u1040\25\u0150\27\u0170\25"
        u"\u0080\27\u0080\25\u092e\27\u10d2\25\u3200\27\u2000\24\u5900\uffff"
        u"\u0200\24"),
        DFA.unpack(u"\12\53"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\53\1\uffff\1\25"
        u"\3\uffff\77\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\54\1\uffff\1\25"
        u"\3\uffff\6\25\1\55\37\25\1\55\30\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\1\34\1\uffff\1\61\2\uffff\12\62"),
        DFA.unpack(u"\1\34\1\uffff\1\63\2\uffff\12\64"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\12\62"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\62\1\uffff\1\25"
        u"\3\uffff\77\25\u0082\uffff\u7f00\25"),
        DFA.unpack(u"\12\64"),
        DFA.unpack(u"\1\25\1\uffff\5\25\5\uffff\3\25\12\64\1\uffff\1\25"
        u"\3\uffff\77\25\u0082\uffff\u7f00\25")
    ]



    DFA20 = DFA




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import LexerMain
    main = LexerMain(QueryLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
