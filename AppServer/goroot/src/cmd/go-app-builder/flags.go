// Copyright 2012 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package main

import (
	"strings"
)

func parseToolFlags(s string) []string {
	// Manual split to handle backslash escaped commas.
	// This doesn't need to be particularly efficient.

	var flags []string
	for s != "" {
		// Find next split point.
		i := -1 // index of last byte checked
		for i < len(s) {
			oi := i
			i = strings.IndexAny(s[i+1:], `,\`)
			if i < 0 {
				break
			}
			i += oi + 1 // map to an index in s
			if s[i] == ',' {
				break
			}
			// skip and unescape escaped character
			s = s[:i] + s[i+1:]
		}

		var arg string
		if i >= 0 {
			arg, s = s[:i], s[i+1:]
		} else {
			// last part
			arg, s = s, ""
		}

		flags = append(flags, arg)
	}
	return flags
}
