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
LT=17
GEO_POINT_FN=29
FIX=30
ESC=34
OCTAL_ESC=36
FUZZY=8
NOT=27
DISTANCE_FN=28
AND=25
ESCAPED_CHAR=40
EOF=-1
LPAREN=23
HAS=22
CHAR_SEQ=37
QUOTE=33
RPAREN=24
START_CHAR=41
ARGS=4
DIGIT=38
EQ=21
NE=20
T__43=43
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


class QueryLexer(Lexer):

    grammarFileName = ""
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







    def mT__43(self, ):

        try:
            _type = T__43
            _channel = DEFAULT_CHANNEL



            pass
            self.match(45)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__44(self, ):

        try:
            _type = T__44
            _channel = DEFAULT_CHANNEL



            pass
            self.match(44)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mT__45(self, ):

        try:
            _type = T__45
            _channel = DEFAULT_CHANNEL



            pass
            self.match(92)



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






    def mREWRITE(self, ):

        try:
            _type = REWRITE
            _channel = DEFAULT_CHANNEL



            pass
            self.match(126)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFIX(self, ):

        try:
            _type = FIX
            _channel = DEFAULT_CHANNEL



            pass
            self.match(43)



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDISTANCE_FN(self, ):

        try:
            _type = DISTANCE_FN
            _channel = DEFAULT_CHANNEL



            pass
            self.match("distance")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mGEO_POINT_FN(self, ):

        try:
            _type = GEO_POINT_FN
            _channel = DEFAULT_CHANNEL



            pass
            self.match("geopoint")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mESC(self, ):

        try:
            _type = ESC
            _channel = DEFAULT_CHANNEL


            alt1 = 3
            LA1_0 = self.input.LA(1)

            if (LA1_0 == 92) :
                LA1 = self.input.LA(2)
                if LA1 == 34 or LA1 == 92:
                    alt1 = 1
                elif LA1 == 117:
                    alt1 = 2
                elif LA1 == 48 or LA1 == 49 or LA1 == 50 or LA1 == 51 or LA1 == 52 or LA1 == 53 or LA1 == 54 or LA1 == 55:
                    alt1 = 3
                else:
                    nvae = NoViableAltException("", 1, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 1, 0, self.input)

                raise nvae

            if alt1 == 1:

                pass
                self.match(92)
                if self.input.LA(1) == 34 or self.input.LA(1) == 92:
                    self.input.consume()
                else:
                    mse = MismatchedSetException(None, self.input)
                    self.recover(mse)
                    raise mse



            elif alt1 == 2:

                pass
                self.mUNICODE_ESC()


            elif alt1 == 3:

                pass
                self.mOCTAL_ESC()


            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mWS(self, ):

        try:
            _type = WS
            _channel = DEFAULT_CHANNEL



            pass
            if (9 <= self.input.LA(1) <= 10) or (12 <= self.input.LA(1) <= 13) or self.input.LA(1) == 32:
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse




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






    def mTEXT(self, ):

        try:
            _type = TEXT
            _channel = DEFAULT_CHANNEL


            alt4 = 2
            LA4_0 = self.input.LA(1)

            if (LA4_0 == 33 or (35 <= LA4_0 <= 39) or LA4_0 == 42 or (46 <= LA4_0 <= 47) or LA4_0 == 59 or (63 <= LA4_0 <= 125) or (161 <= LA4_0 <= 65518)) :
                alt4 = 1
            elif (LA4_0 == 45 or (48 <= LA4_0 <= 57)) :
                alt4 = 2
            else:
                nvae = NoViableAltException("", 4, 0, self.input)

                raise nvae

            if alt4 == 1:

                pass
                self.mCHAR_SEQ()


            elif alt4 == 2:

                pass

                alt2 = 2
                LA2_0 = self.input.LA(1)

                if (LA2_0 == 45) :
                    alt2 = 1
                if alt2 == 1:

                    pass
                    self.match(45)



                self.mDIGIT()

                while True:
                    alt3 = 5
                    LA3_0 = self.input.LA(1)

                    if (LA3_0 == 33 or (35 <= LA3_0 <= 39) or (42 <= LA3_0 <= 43) or (45 <= LA3_0 <= 57) or LA3_0 == 59 or (63 <= LA3_0 <= 91) or (93 <= LA3_0 <= 125) or (161 <= LA3_0 <= 65518)) :
                        alt3 = 1
                    elif (LA3_0 == 92) :
                        LA3 = self.input.LA(2)
                        if LA3 == 34 or LA3 == 43 or LA3 == 44 or LA3 == 58 or LA3 == 60 or LA3 == 61 or LA3 == 62 or LA3 == 92 or LA3 == 126:
                            alt3 = 2
                        elif LA3 == 117:
                            alt3 = 3
                        elif LA3 == 48 or LA3 == 49 or LA3 == 50 or LA3 == 51 or LA3 == 52 or LA3 == 53 or LA3 == 54 or LA3 == 55:
                            alt3 = 4



                    if alt3 == 1:

                        pass
                        self.mMID_CHAR()


                    elif alt3 == 2:

                        pass
                        self.mESCAPED_CHAR()


                    elif alt3 == 3:

                        pass
                        self.mUNICODE_ESC()


                    elif alt3 == 4:

                        pass
                        self.mOCTAL_ESC()


                    else:
                        break




            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mCHAR_SEQ(self, ):

        try:


            pass

            alt5 = 4
            LA5_0 = self.input.LA(1)

            if (LA5_0 == 33 or (35 <= LA5_0 <= 39) or LA5_0 == 42 or (46 <= LA5_0 <= 47) or LA5_0 == 59 or (63 <= LA5_0 <= 91) or (93 <= LA5_0 <= 125) or (161 <= LA5_0 <= 65518)) :
                alt5 = 1
            elif (LA5_0 == 92) :
                LA5 = self.input.LA(2)
                if LA5 == 34 or LA5 == 43 or LA5 == 44 or LA5 == 58 or LA5 == 60 or LA5 == 61 or LA5 == 62 or LA5 == 92 or LA5 == 126:
                    alt5 = 2
                elif LA5 == 117:
                    alt5 = 3
                elif LA5 == 48 or LA5 == 49 or LA5 == 50 or LA5 == 51 or LA5 == 52 or LA5 == 53 or LA5 == 54 or LA5 == 55:
                    alt5 = 4
                else:
                    nvae = NoViableAltException("", 5, 2, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 5, 0, self.input)

                raise nvae

            if alt5 == 1:

                pass
                self.mSTART_CHAR()


            elif alt5 == 2:

                pass
                self.mESCAPED_CHAR()


            elif alt5 == 3:

                pass
                self.mUNICODE_ESC()


            elif alt5 == 4:

                pass
                self.mOCTAL_ESC()




            while True:
                alt6 = 5
                LA6_0 = self.input.LA(1)

                if (LA6_0 == 33 or (35 <= LA6_0 <= 39) or (42 <= LA6_0 <= 43) or (45 <= LA6_0 <= 57) or LA6_0 == 59 or (63 <= LA6_0 <= 91) or (93 <= LA6_0 <= 125) or (161 <= LA6_0 <= 65518)) :
                    alt6 = 1
                elif (LA6_0 == 92) :
                    LA6 = self.input.LA(2)
                    if LA6 == 34 or LA6 == 43 or LA6 == 44 or LA6 == 58 or LA6 == 60 or LA6 == 61 or LA6 == 62 or LA6 == 92 or LA6 == 126:
                        alt6 = 2
                    elif LA6 == 117:
                        alt6 = 3
                    elif LA6 == 48 or LA6 == 49 or LA6 == 50 or LA6 == 51 or LA6 == 52 or LA6 == 53 or LA6 == 54 or LA6 == 55:
                        alt6 = 4



                if alt6 == 1:

                    pass
                    self.mMID_CHAR()


                elif alt6 == 2:

                    pass
                    self.mESCAPED_CHAR()


                elif alt6 == 3:

                    pass
                    self.mUNICODE_ESC()


                elif alt6 == 4:

                    pass
                    self.mOCTAL_ESC()


                else:
                    break






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






    def mOCTAL_ESC(self, ):

        try:

            alt7 = 3
            LA7_0 = self.input.LA(1)

            if (LA7_0 == 92) :
                LA7_1 = self.input.LA(2)

                if ((48 <= LA7_1 <= 51)) :
                    LA7_2 = self.input.LA(3)

                    if ((48 <= LA7_2 <= 55)) :
                        LA7_4 = self.input.LA(4)

                        if ((48 <= LA7_4 <= 55)) :
                            alt7 = 1
                        else:
                            alt7 = 2
                    else:
                        alt7 = 3
                elif ((52 <= LA7_1 <= 55)) :
                    LA7_3 = self.input.LA(3)

                    if ((48 <= LA7_3 <= 55)) :
                        alt7 = 2
                    else:
                        alt7 = 3
                else:
                    nvae = NoViableAltException("", 7, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 7, 0, self.input)

                raise nvae

            if alt7 == 1:

                pass
                self.match(92)


                pass
                self.matchRange(48, 51)





                pass
                self.matchRange(48, 55)





                pass
                self.matchRange(48, 55)





            elif alt7 == 2:

                pass
                self.match(92)


                pass
                self.matchRange(48, 55)





                pass
                self.matchRange(48, 55)





            elif alt7 == 3:

                pass
                self.match(92)


                pass
                self.matchRange(48, 55)






        finally:

            pass






    def mDIGIT(self, ):

        try:


            pass
            self.matchRange(48, 57)




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






    def mSTART_CHAR(self, ):

        try:


            pass
            if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or self.input.LA(1) == 42 or (46 <= self.input.LA(1) <= 47) or self.input.LA(1) == 59 or (63 <= self.input.LA(1) <= 91) or (93 <= self.input.LA(1) <= 125) or (161 <= self.input.LA(1) <= 65518):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mMID_CHAR(self, ):

        try:


            pass
            if self.input.LA(1) == 33 or (35 <= self.input.LA(1) <= 39) or (42 <= self.input.LA(1) <= 43) or (45 <= self.input.LA(1) <= 57) or self.input.LA(1) == 59 or (63 <= self.input.LA(1) <= 91) or (93 <= self.input.LA(1) <= 125) or (161 <= self.input.LA(1) <= 65518):
                self.input.consume()
            else:
                mse = MismatchedSetException(None, self.input)
                self.recover(mse)
                raise mse





        finally:

            pass






    def mESCAPED_CHAR(self, ):

        try:

            alt8 = 9
            alt8 = self.dfa8.predict(self.input)
            if alt8 == 1:

                pass
                self.match("\\,")


            elif alt8 == 2:

                pass
                self.match("\\:")


            elif alt8 == 3:

                pass
                self.match("\\=")


            elif alt8 == 4:

                pass
                self.match("\\<")


            elif alt8 == 5:

                pass
                self.match("\\>")


            elif alt8 == 6:

                pass
                self.match("\\+")


            elif alt8 == 7:

                pass
                self.match("\\~")


            elif alt8 == 8:

                pass
                self.match("\\\"")


            elif alt8 == 9:

                pass
                self.match("\\\\")



        finally:

            pass





    def mTokens(self):

        alt9 = 23
        alt9 = self.dfa9.predict(self.input)
        if alt9 == 1:

            pass
            self.mT__43()


        elif alt9 == 2:

            pass
            self.mT__44()


        elif alt9 == 3:

            pass
            self.mT__45()


        elif alt9 == 4:

            pass
            self.mHAS()


        elif alt9 == 5:

            pass
            self.mOR()


        elif alt9 == 6:

            pass
            self.mAND()


        elif alt9 == 7:

            pass
            self.mNOT()


        elif alt9 == 8:

            pass
            self.mREWRITE()


        elif alt9 == 9:

            pass
            self.mFIX()


        elif alt9 == 10:

            pass
            self.mDISTANCE_FN()


        elif alt9 == 11:

            pass
            self.mGEO_POINT_FN()


        elif alt9 == 12:

            pass
            self.mESC()


        elif alt9 == 13:

            pass
            self.mWS()


        elif alt9 == 14:

            pass
            self.mLPAREN()


        elif alt9 == 15:

            pass
            self.mRPAREN()


        elif alt9 == 16:

            pass
            self.mLT()


        elif alt9 == 17:

            pass
            self.mGT()


        elif alt9 == 18:

            pass
            self.mGE()


        elif alt9 == 19:

            pass
            self.mLE()


        elif alt9 == 20:

            pass
            self.mNE()


        elif alt9 == 21:

            pass
            self.mEQ()


        elif alt9 == 22:

            pass
            self.mQUOTE()


        elif alt9 == 23:

            pass
            self.mTEXT()









    DFA8_eot = DFA.unpack(
        u"\13\uffff"
        )

    DFA8_eof = DFA.unpack(
        u"\13\uffff"
        )

    DFA8_min = DFA.unpack(
        u"\1\134\1\42\11\uffff"
        )

    DFA8_max = DFA.unpack(
        u"\1\134\1\176\11\uffff"
        )

    DFA8_accept = DFA.unpack(
        u"\2\uffff\1\1\1\2\1\3\1\4\1\5\1\6\1\7\1\10\1\11"
        )

    DFA8_special = DFA.unpack(
        u"\13\uffff"
        )


    DFA8_transition = [
        DFA.unpack(u"\1\1"),
        DFA.unpack(u"\1\11\10\uffff\1\7\1\2\15\uffff\1\3\1\uffff\1\5\1\4"
        u"\1\6\35\uffff\1\12\41\uffff\1\10"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA8 = DFA


    DFA9_eot = DFA.unpack(
        u"\1\uffff\1\25\1\uffff\1\33\1\uffff\3\24\2\uffff\2\24\3\uffff\1"
        u"\42\1\44\1\24\4\uffff\1\46\1\uffff\3\46\1\uffff\1\52\4\24\7\uffff"
        u"\2\46\1\uffff\1\61\1\62\2\24\1\uffff\1\46\2\uffff\2\24\1\uffff"
        u"\2\24\1\46\4\24\1\77\1\100\2\uffff"
        )

    DFA9_eof = DFA.unpack(
        u"\101\uffff"
        )

    DFA9_min = DFA.unpack(
        u"\1\11\1\60\1\uffff\1\42\1\uffff\1\122\1\116\1\117\2\uffff\1\151"
        u"\1\145\3\uffff\3\75\4\uffff\1\41\1\60\3\41\1\uffff\1\41\1\104\1"
        u"\124\1\163\1\157\6\uffff\1\60\2\41\1\uffff\2\41\1\164\1\160\1\60"
        u"\1\41\2\uffff\1\141\1\157\1\60\1\156\1\151\1\41\1\143\1\156\1\145"
        u"\1\164\2\41\2\uffff"
        )

    DFA9_max = DFA.unpack(
        u"\1\uffee\1\71\1\uffff\1\176\1\uffff\1\122\1\116\1\117\2\uffff\1"
        u"\151\1\145\3\uffff\3\75\4\uffff\1\uffee\1\146\3\uffee\1\uffff\1"
        u"\uffee\1\104\1\124\1\163\1\157\6\uffff\1\146\2\uffee\1\uffff\2"
        u"\uffee\1\164\1\160\1\146\1\uffee\2\uffff\1\141\1\157\1\146\1\156"
        u"\1\151\1\uffee\1\143\1\156\1\145\1\164\2\uffee\2\uffff"
        )

    DFA9_accept = DFA.unpack(
        u"\2\uffff\1\2\1\uffff\1\4\3\uffff\1\10\1\11\2\uffff\1\15\1\16\1"
        u"\17\3\uffff\1\25\1\26\1\27\1\1\5\uffff\1\3\5\uffff\1\23\1\20\1"
        u"\22\1\21\1\24\1\14\3\uffff\1\5\6\uffff\1\6\1\7\14\uffff\1\12\1"
        u"\13"
        )

    DFA9_special = DFA.unpack(
        u"\101\uffff"
        )


    DFA9_transition = [
        DFA.unpack(u"\2\14\1\uffff\2\14\22\uffff\1\14\1\21\1\23\5\24\1\15"
        u"\1\16\1\24\1\11\1\2\1\1\14\24\1\4\1\24\1\17\1\22\1\20\2\24\1\6"
        u"\14\24\1\7\1\5\14\24\1\3\7\24\1\12\2\24\1\13\26\24\1\10\42\uffff"
        u"\uff4e\24"),
        DFA.unpack(u"\12\24"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\26\10\uffff\2\24\3\uffff\4\31\4\32\2\uffff\1\24"
        u"\1\uffff\3\24\35\uffff\1\30\30\uffff\1\27\10\uffff\1\24"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\34"),
        DFA.unpack(u"\1\35"),
        DFA.unpack(u"\1\36"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\37"),
        DFA.unpack(u"\1\40"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\41"),
        DFA.unpack(u"\1\43"),
        DFA.unpack(u"\1\45"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\12\47\7\uffff\6\47\32\uffff\6\47"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\3\24\10\50"
        u"\2\24\1\uffff\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\3\24\10\51"
        u"\2\24\1\uffff\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\53"),
        DFA.unpack(u"\1\54"),
        DFA.unpack(u"\1\55"),
        DFA.unpack(u"\1\56"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\12\57\7\uffff\6\57\32\uffff\6\57"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\3\24\10\60"
        u"\2\24\1\uffff\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\63"),
        DFA.unpack(u"\1\64"),
        DFA.unpack(u"\12\65\7\uffff\6\65\32\uffff\6\65"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\66"),
        DFA.unpack(u"\1\67"),
        DFA.unpack(u"\12\70\7\uffff\6\70\32\uffff\6\70"),
        DFA.unpack(u"\1\71"),
        DFA.unpack(u"\1\72"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\73"),
        DFA.unpack(u"\1\74"),
        DFA.unpack(u"\1\75"),
        DFA.unpack(u"\1\76"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u"\1\24\1\uffff\5\24\2\uffff\2\24\1\uffff\15\24\1\uffff"
        u"\1\24\3\uffff\77\24\43\uffff\uff4e\24"),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    DFA9 = DFA




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from google.appengine._internal.antlr3.main import LexerMain
    main = LexerMain(QueryLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
