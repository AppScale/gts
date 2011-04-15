# generate package list from control file.

BEGIN {
  flag = 0
  count = 1
}

/^Depends:/ {
    flag = 1
}

/^ / {
    if (flag != 0) {
#	gsub(" ", "", $0)
	split($0, list, ",");
	for (i in list) {
	    if (length(list[i]) > 0) {
		gsub("\(.+\)", "", list[i])
		packages[count] = list[i]
		count += 1
	    }
	}
    }
}

/^Description:/ {
    flag = 0
}

END {
    for (i in packages)
	printf("%s ", packages[i])
}
