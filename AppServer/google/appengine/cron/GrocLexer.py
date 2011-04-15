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
from antlr3 import *
from antlr3.compat import set, frozenset



HIDDEN = BaseRecognizer.HIDDEN


THIRD=13
SEPTEMBER=36
WEDNESDAY=22
JULY=34
APRIL=31
DIGITS=8
OCTOBER=37
MAY=32
DAY=19
MARCH=30
EOF=-1
MONTH=27
FRIDAY=24
UNKNOWN_TOKEN=44
TIME=5
SYNCHRONIZED=9
QUARTER=40
COMMA=10
DIGIT=7
FOURTH=14
SECOND=12
NOVEMBER=38
SATURDAY=25
TO=42
EVERY=6
FEBRUARY=29
MONDAY=20
SUNDAY=26
JUNE=33
OF=4
JANUARY=28
MINUTES=18
FIFTH=15
WS=43
THURSDAY=23
DECEMBER=39
AUGUST=35
FROM=41
TUESDAY=21
HOURS=17
FIRST=11
FOURTH_OR_FIFTH=16


class GrocLexer(Lexer):

    grammarFileName = "Groc.g"
    antlr_version = version_str_to_tuple("3.1.1")
    antlr_version_str = "3.1.1"

    def __init__(self, input=None, state=None):
        if state is None:
            state = RecognizerSharedState()
        Lexer.__init__(self, input, state)

        self.dfa25 = self.DFA25(
            self, 25,
            eot = self.DFA25_eot,
            eof = self.DFA25_eof,
            min = self.DFA25_min,
            max = self.DFA25_max,
            accept = self.DFA25_accept,
            special = self.DFA25_special,
            transition = self.DFA25_transition
            )







    def mTIME(self, ):

        try:
            _type = TIME
            _channel = DEFAULT_CHANNEL



            pass

            alt1 = 4
            LA1 = self.input.LA(1)
            if LA1 == 48:
                LA1_1 = self.input.LA(2)

                if (LA1_1 == 58) :
                    alt1 = 1
                elif ((48 <= LA1_1 <= 57)) :
                    alt1 = 2
                else:
                    nvae = NoViableAltException("", 1, 1, self.input)

                    raise nvae

            elif LA1 == 49:
                LA1_2 = self.input.LA(2)

                if (LA1_2 == 58) :
                    alt1 = 1
                elif ((48 <= LA1_2 <= 57)) :
                    alt1 = 3
                else:
                    nvae = NoViableAltException("", 1, 2, self.input)

                    raise nvae

            elif LA1 == 50:
                LA1_3 = self.input.LA(2)

                if ((48 <= LA1_3 <= 51)) :
                    alt1 = 4
                elif (LA1_3 == 58) :
                    alt1 = 1
                else:
                    nvae = NoViableAltException("", 1, 3, self.input)

                    raise nvae

            elif LA1 == 51 or LA1 == 52 or LA1 == 53 or LA1 == 54 or LA1 == 55 or LA1 == 56 or LA1 == 57:
                alt1 = 1
            else:
                nvae = NoViableAltException("", 1, 0, self.input)

                raise nvae

            if alt1 == 1:

                pass
                self.mDIGIT()


            elif alt1 == 2:

                pass


                pass
                self.match(48)
                self.mDIGIT()





            elif alt1 == 3:

                pass


                pass
                self.match(49)
                self.mDIGIT()





            elif alt1 == 4:

                pass


                pass
                self.match(50)
                self.matchRange(48, 51)






            self.match(58)


            pass
            self.matchRange(48, 53)
            self.mDIGIT()






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSYNCHRONIZED(self, ):

        try:
            _type = SYNCHRONIZED
            _channel = DEFAULT_CHANNEL



            pass
            self.match("synchronized")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFIRST(self, ):

        try:
            _type = FIRST
            _channel = DEFAULT_CHANNEL



            pass

            alt2 = 2
            LA2_0 = self.input.LA(1)

            if (LA2_0 == 49) :
                alt2 = 1
            elif (LA2_0 == 102) :
                alt2 = 2
            else:
                nvae = NoViableAltException("", 2, 0, self.input)

                raise nvae

            if alt2 == 1:

                pass
                self.match("1st")


            elif alt2 == 2:

                pass
                self.match("first")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSECOND(self, ):

        try:
            _type = SECOND
            _channel = DEFAULT_CHANNEL



            pass

            alt3 = 2
            LA3_0 = self.input.LA(1)

            if (LA3_0 == 50) :
                alt3 = 1
            elif (LA3_0 == 115) :
                alt3 = 2
            else:
                nvae = NoViableAltException("", 3, 0, self.input)

                raise nvae

            if alt3 == 1:

                pass
                self.match("2nd")


            elif alt3 == 2:

                pass
                self.match("second")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTHIRD(self, ):

        try:
            _type = THIRD
            _channel = DEFAULT_CHANNEL



            pass

            alt4 = 2
            LA4_0 = self.input.LA(1)

            if (LA4_0 == 51) :
                alt4 = 1
            elif (LA4_0 == 116) :
                alt4 = 2
            else:
                nvae = NoViableAltException("", 4, 0, self.input)

                raise nvae

            if alt4 == 1:

                pass
                self.match("3rd")


            elif alt4 == 2:

                pass
                self.match("third")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFOURTH(self, ):

        try:
            _type = FOURTH
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("4th")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFIFTH(self, ):

        try:
            _type = FIFTH
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("5th")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFOURTH_OR_FIFTH(self, ):

        try:
            _type = FOURTH_OR_FIFTH
            _channel = DEFAULT_CHANNEL



            pass

            alt5 = 2
            LA5_0 = self.input.LA(1)

            if (LA5_0 == 102) :
                LA5_1 = self.input.LA(2)

                if (LA5_1 == 111) :
                    alt5 = 1
                elif (LA5_1 == 105) :
                    alt5 = 2
                else:
                    nvae = NoViableAltException("", 5, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 5, 0, self.input)

                raise nvae

            if alt5 == 1:

                pass


                pass
                self.match("fourth")

                _type = FOURTH;






            elif alt5 == 2:

                pass


                pass
                self.match("fifth")

                _type = FIFTH;










            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDAY(self, ):

        try:
            _type = DAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("day")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMONDAY(self, ):

        try:
            _type = MONDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("mon")

            alt6 = 2
            LA6_0 = self.input.LA(1)

            if (LA6_0 == 100) :
                alt6 = 1
            if alt6 == 1:

                pass
                self.match("day")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTUESDAY(self, ):

        try:
            _type = TUESDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("tue")

            alt7 = 2
            LA7_0 = self.input.LA(1)

            if (LA7_0 == 115) :
                alt7 = 1
            if alt7 == 1:

                pass
                self.match("sday")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mWEDNESDAY(self, ):

        try:
            _type = WEDNESDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("wed")

            alt8 = 2
            LA8_0 = self.input.LA(1)

            if (LA8_0 == 110) :
                alt8 = 1
            if alt8 == 1:

                pass
                self.match("nesday")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTHURSDAY(self, ):

        try:
            _type = THURSDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("thu")

            alt9 = 2
            LA9_0 = self.input.LA(1)

            if (LA9_0 == 114) :
                alt9 = 1
            if alt9 == 1:

                pass
                self.match("rsday")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFRIDAY(self, ):

        try:
            _type = FRIDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("fri")

            alt10 = 2
            LA10_0 = self.input.LA(1)

            if (LA10_0 == 100) :
                alt10 = 1
            if alt10 == 1:

                pass
                self.match("day")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSATURDAY(self, ):

        try:
            _type = SATURDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("sat")

            alt11 = 2
            LA11_0 = self.input.LA(1)

            if (LA11_0 == 117) :
                alt11 = 1
            if alt11 == 1:

                pass
                self.match("urday")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSUNDAY(self, ):

        try:
            _type = SUNDAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("sun")

            alt12 = 2
            LA12_0 = self.input.LA(1)

            if (LA12_0 == 100) :
                alt12 = 1
            if alt12 == 1:

                pass
                self.match("day")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mJANUARY(self, ):

        try:
            _type = JANUARY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("jan")

            alt13 = 2
            LA13_0 = self.input.LA(1)

            if (LA13_0 == 117) :
                alt13 = 1
            if alt13 == 1:

                pass
                self.match("uary")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFEBRUARY(self, ):

        try:
            _type = FEBRUARY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("feb")

            alt14 = 2
            LA14_0 = self.input.LA(1)

            if (LA14_0 == 114) :
                alt14 = 1
            if alt14 == 1:

                pass
                self.match("ruary")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMARCH(self, ):

        try:
            _type = MARCH
            _channel = DEFAULT_CHANNEL



            pass
            self.match("mar")

            alt15 = 2
            LA15_0 = self.input.LA(1)

            if (LA15_0 == 99) :
                alt15 = 1
            if alt15 == 1:

                pass
                self.match("ch")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mAPRIL(self, ):

        try:
            _type = APRIL
            _channel = DEFAULT_CHANNEL



            pass
            self.match("apr")

            alt16 = 2
            LA16_0 = self.input.LA(1)

            if (LA16_0 == 105) :
                alt16 = 1
            if alt16 == 1:

                pass
                self.match("il")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMAY(self, ):

        try:
            _type = MAY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("may")



            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mJUNE(self, ):

        try:
            _type = JUNE
            _channel = DEFAULT_CHANNEL



            pass
            self.match("jun")

            alt17 = 2
            LA17_0 = self.input.LA(1)

            if (LA17_0 == 101) :
                alt17 = 1
            if alt17 == 1:

                pass
                self.match(101)






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mJULY(self, ):

        try:
            _type = JULY
            _channel = DEFAULT_CHANNEL



            pass
            self.match("jul")

            alt18 = 2
            LA18_0 = self.input.LA(1)

            if (LA18_0 == 121) :
                alt18 = 1
            if alt18 == 1:

                pass
                self.match(121)






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mAUGUST(self, ):

        try:
            _type = AUGUST
            _channel = DEFAULT_CHANNEL



            pass
            self.match("aug")

            alt19 = 2
            LA19_0 = self.input.LA(1)

            if (LA19_0 == 117) :
                alt19 = 1
            if alt19 == 1:

                pass
                self.match("ust")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mSEPTEMBER(self, ):

        try:
            _type = SEPTEMBER
            _channel = DEFAULT_CHANNEL



            pass
            self.match("sep")

            alt20 = 2
            LA20_0 = self.input.LA(1)

            if (LA20_0 == 116) :
                alt20 = 1
            if alt20 == 1:

                pass
                self.match("tember")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mOCTOBER(self, ):

        try:
            _type = OCTOBER
            _channel = DEFAULT_CHANNEL



            pass
            self.match("oct")

            alt21 = 2
            LA21_0 = self.input.LA(1)

            if (LA21_0 == 111) :
                alt21 = 1
            if alt21 == 1:

                pass
                self.match("ober")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mNOVEMBER(self, ):

        try:
            _type = NOVEMBER
            _channel = DEFAULT_CHANNEL



            pass
            self.match("nov")

            alt22 = 2
            LA22_0 = self.input.LA(1)

            if (LA22_0 == 101) :
                alt22 = 1
            if alt22 == 1:

                pass
                self.match("ember")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDECEMBER(self, ):

        try:
            _type = DECEMBER
            _channel = DEFAULT_CHANNEL



            pass
            self.match("dec")

            alt23 = 2
            LA23_0 = self.input.LA(1)

            if (LA23_0 == 101) :
                alt23 = 1
            if alt23 == 1:

                pass
                self.match("ember")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMONTH(self, ):

        try:
            _type = MONTH
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("month")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mQUARTER(self, ):

        try:
            _type = QUARTER
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("quarter")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mEVERY(self, ):

        try:
            _type = EVERY
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("every")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mHOURS(self, ):

        try:
            _type = HOURS
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("hours")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mMINUTES(self, ):

        try:
            _type = MINUTES
            _channel = DEFAULT_CHANNEL



            pass

            alt24 = 2
            LA24_0 = self.input.LA(1)

            if (LA24_0 == 109) :
                LA24_1 = self.input.LA(2)

                if (LA24_1 == 105) :
                    LA24_2 = self.input.LA(3)

                    if (LA24_2 == 110) :
                        LA24_3 = self.input.LA(4)

                        if (LA24_3 == 115) :
                            alt24 = 1
                        elif (LA24_3 == 117) :
                            alt24 = 2
                        else:
                            nvae = NoViableAltException("", 24, 3, self.input)

                            raise nvae

                    else:
                        nvae = NoViableAltException("", 24, 2, self.input)

                        raise nvae

                else:
                    nvae = NoViableAltException("", 24, 1, self.input)

                    raise nvae

            else:
                nvae = NoViableAltException("", 24, 0, self.input)

                raise nvae

            if alt24 == 1:

                pass
                self.match("mins")


            elif alt24 == 2:

                pass
                self.match("minutes")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mCOMMA(self, ):

        try:
            _type = COMMA
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match(44)






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mOF(self, ):

        try:
            _type = OF
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("of")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mFROM(self, ):

        try:
            _type = FROM
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("from")






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mTO(self, ):

        try:
            _type = TO
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.match("to")






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


            _channel=HIDDEN;




            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDIGIT(self, ):

        try:
            _type = DIGIT
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.matchRange(48, 57)






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mDIGITS(self, ):

        try:
            _type = DIGITS
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.mDIGIT()
            self.mDIGIT()






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass






    def mUNKNOWN_TOKEN(self, ):

        try:
            _type = UNKNOWN_TOKEN
            _channel = DEFAULT_CHANNEL



            pass


            pass
            self.matchAny()






            self._state.type = _type
            self._state.channel = _channel

        finally:

            pass





    def mTokens(self):

        alt25 = 41
        alt25 = self.dfa25.predict(self.input)
        if alt25 == 1:

            pass
            self.mTIME()


        elif alt25 == 2:

            pass
            self.mSYNCHRONIZED()


        elif alt25 == 3:

            pass
            self.mFIRST()


        elif alt25 == 4:

            pass
            self.mSECOND()


        elif alt25 == 5:

            pass
            self.mTHIRD()


        elif alt25 == 6:

            pass
            self.mFOURTH()


        elif alt25 == 7:

            pass
            self.mFIFTH()


        elif alt25 == 8:

            pass
            self.mFOURTH_OR_FIFTH()


        elif alt25 == 9:

            pass
            self.mDAY()


        elif alt25 == 10:

            pass
            self.mMONDAY()


        elif alt25 == 11:

            pass
            self.mTUESDAY()


        elif alt25 == 12:

            pass
            self.mWEDNESDAY()


        elif alt25 == 13:

            pass
            self.mTHURSDAY()


        elif alt25 == 14:

            pass
            self.mFRIDAY()


        elif alt25 == 15:

            pass
            self.mSATURDAY()


        elif alt25 == 16:

            pass
            self.mSUNDAY()


        elif alt25 == 17:

            pass
            self.mJANUARY()


        elif alt25 == 18:

            pass
            self.mFEBRUARY()


        elif alt25 == 19:

            pass
            self.mMARCH()


        elif alt25 == 20:

            pass
            self.mAPRIL()


        elif alt25 == 21:

            pass
            self.mMAY()


        elif alt25 == 22:

            pass
            self.mJUNE()


        elif alt25 == 23:

            pass
            self.mJULY()


        elif alt25 == 24:

            pass
            self.mAUGUST()


        elif alt25 == 25:

            pass
            self.mSEPTEMBER()


        elif alt25 == 26:

            pass
            self.mOCTOBER()


        elif alt25 == 27:

            pass
            self.mNOVEMBER()


        elif alt25 == 28:

            pass
            self.mDECEMBER()


        elif alt25 == 29:

            pass
            self.mMONTH()


        elif alt25 == 30:

            pass
            self.mQUARTER()


        elif alt25 == 31:

            pass
            self.mEVERY()


        elif alt25 == 32:

            pass
            self.mHOURS()


        elif alt25 == 33:

            pass
            self.mMINUTES()


        elif alt25 == 34:

            pass
            self.mCOMMA()


        elif alt25 == 35:

            pass
            self.mOF()


        elif alt25 == 36:

            pass
            self.mFROM()


        elif alt25 == 37:

            pass
            self.mTO()


        elif alt25 == 38:

            pass
            self.mWS()


        elif alt25 == 39:

            pass
            self.mDIGIT()


        elif alt25 == 40:

            pass
            self.mDIGITS()


        elif alt25 == 41:

            pass
            self.mUNKNOWN_TOKEN()









    DFA25_eot = DFA.unpack(
        u"\1\uffff\4\31\2\27\1\31\1\27\2\31\12\27\3\uffff\1\37\3\uffff\2"
        u"\37\46\uffff\1\112\6\uffff"
        )

    DFA25_eof = DFA.unpack(
        u"\113\uffff"
        )

    DFA25_min = DFA.unpack(
        u"\1\0\4\60\1\141\1\145\1\60\1\150\2\60\2\141\1\145\1\141\1\160\1"
        u"\143\1\157\1\165\1\166\1\157\3\uffff\1\72\3\uffff\2\72\4\uffff"
        u"\1\143\2\uffff\1\146\1\uffff\1\151\2\uffff\1\151\5\uffff\1\156"
        u"\1\162\3\uffff\1\154\16\uffff\1\164\6\uffff"
        )

    DFA25_max = DFA.unpack(
        u"\1\uffff\1\72\1\163\1\156\1\162\1\171\1\162\1\164\1\165\1\164\1"
        u"\72\1\145\1\157\1\145\2\165\1\146\1\157\1\165\1\166\1\157\3\uffff"
        u"\1\72\3\uffff\2\72\4\uffff\1\160\2\uffff\1\162\1\uffff\1\157\2"
        u"\uffff\1\165\5\uffff\1\156\1\171\3\uffff\1\156\16\uffff\1\164\6"
        u"\uffff"
        )

    DFA25_accept = DFA.unpack(
        u"\25\uffff\1\42\1\46\1\51\1\uffff\1\47\1\1\1\3\2\uffff\1\4\1\50"
        u"\1\5\1\2\1\uffff\1\17\1\20\1\uffff\1\10\1\uffff\1\22\1\6\1\uffff"
        u"\1\13\1\45\1\7\1\11\1\34\2\uffff\1\41\1\14\1\21\1\uffff\1\24\1"
        u"\30\1\32\1\43\1\33\1\36\1\37\1\40\1\42\1\46\1\31\1\16\1\44\1\15"
        u"\1\uffff\1\23\1\25\1\26\1\27\1\35\1\12"
        )

    DFA25_special = DFA.unpack(
        u"\1\0\112\uffff"
        )


    DFA25_transition = [
        DFA.unpack(u"\11\27\2\26\2\27\1\26\22\27\1\26\13\27\1\25\3\27\1\1"
        u"\1\2\1\3\1\4\1\7\1\11\4\12\47\27\1\17\2\27\1\13\1\23\1\6\1\27\1"
        u"\24\1\27\1\16\2\27\1\14\1\21\1\20\1\27\1\22\1\27\1\5\1\10\2\27"
        u"\1\15\uff88\27"),
        DFA.unpack(u"\12\30\1\32"),
        DFA.unpack(u"\12\34\1\32\70\uffff\1\33"),
        DFA.unpack(u"\4\35\6\37\1\32\63\uffff\1\36"),
        DFA.unpack(u"\12\37\1\32\67\uffff\1\40"),
        DFA.unpack(u"\1\43\3\uffff\1\42\17\uffff\1\44\3\uffff\1\41"),
        DFA.unpack(u"\1\50\3\uffff\1\45\5\uffff\1\46\2\uffff\1\47"),
        DFA.unpack(u"\12\37\1\32\71\uffff\1\51"),
        DFA.unpack(u"\1\52\6\uffff\1\54\5\uffff\1\53"),
        DFA.unpack(u"\12\37\1\32\71\uffff\1\55"),
        DFA.unpack(u"\12\37\1\32"),
        DFA.unpack(u"\1\56\3\uffff\1\57"),
        DFA.unpack(u"\1\61\7\uffff\1\62\5\uffff\1\60"),
        DFA.unpack(u"\1\63"),
        DFA.unpack(u"\1\64\23\uffff\1\65"),
        DFA.unpack(u"\1\66\4\uffff\1\67"),
        DFA.unpack(u"\1\70\2\uffff\1\71"),
        DFA.unpack(u"\1\72"),
        DFA.unpack(u"\1\73"),
        DFA.unpack(u"\1\74"),
        DFA.unpack(u"\1\75"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\32"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\32"),
        DFA.unpack(u"\1\32"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\36\14\uffff\1\100"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\46\13\uffff\1\33"),
        DFA.unpack(u""),
        DFA.unpack(u"\1\101\5\uffff\1\102"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\40\13\uffff\1\103"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\104"),
        DFA.unpack(u"\1\105\6\uffff\1\106"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\110\1\uffff\1\107"),
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
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"\1\111"),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u""),
        DFA.unpack(u"")
    ]



    class DFA25(DFA):
        def specialStateTransition(self_, s, input):





            self = self_.recognizer

            _s = s

            if s == 0:
                LA25_0 = input.LA(1)

                s = -1
                if (LA25_0 == 48):
                    s = 1

                elif (LA25_0 == 49):
                    s = 2

                elif (LA25_0 == 50):
                    s = 3

                elif (LA25_0 == 51):
                    s = 4

                elif (LA25_0 == 115):
                    s = 5

                elif (LA25_0 == 102):
                    s = 6

                elif (LA25_0 == 52):
                    s = 7

                elif (LA25_0 == 116):
                    s = 8

                elif (LA25_0 == 53):
                    s = 9

                elif ((54 <= LA25_0 <= 57)):
                    s = 10

                elif (LA25_0 == 100):
                    s = 11

                elif (LA25_0 == 109):
                    s = 12

                elif (LA25_0 == 119):
                    s = 13

                elif (LA25_0 == 106):
                    s = 14

                elif (LA25_0 == 97):
                    s = 15

                elif (LA25_0 == 111):
                    s = 16

                elif (LA25_0 == 110):
                    s = 17

                elif (LA25_0 == 113):
                    s = 18

                elif (LA25_0 == 101):
                    s = 19

                elif (LA25_0 == 104):
                    s = 20

                elif (LA25_0 == 44):
                    s = 21

                elif ((9 <= LA25_0 <= 10) or LA25_0 == 13 or LA25_0 == 32):
                    s = 22

                elif ((0 <= LA25_0 <= 8) or (11 <= LA25_0 <= 12) or (14 <= LA25_0 <= 31) or (33 <= LA25_0 <= 43) or (45 <= LA25_0 <= 47) or (58 <= LA25_0 <= 96) or (98 <= LA25_0 <= 99) or LA25_0 == 103 or LA25_0 == 105 or (107 <= LA25_0 <= 108) or LA25_0 == 112 or LA25_0 == 114 or (117 <= LA25_0 <= 118) or (120 <= LA25_0 <= 65535)):
                    s = 23

                if s >= 0:
                    return s

            nvae = NoViableAltException(self_.getDescription(), 25, _s, input)
            self_.error(nvae)
            raise nvae




def main(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    from antlr3.main import LexerMain
    main = LexerMain(GrocLexer)
    main.stdin = stdin
    main.stdout = stdout
    main.stderr = stderr
    main.execute(argv)


if __name__ == '__main__':
    main(sys.argv)
