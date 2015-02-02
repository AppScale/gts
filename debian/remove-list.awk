# Generate package list from control file.

BEGIN {
  count = 1
  flag = 0
}

# This finds all the conflicts, but stops at the first stanza afterward (for
# example, Descriptions).
/^(Conflicts):/,/^Description:/ {
    if (gsub("^Conflicts:", "")) { flag = 1 }
    if ($0 !~ /^[ \t]/) { flag = 0 }    # Stop at the first stanza.
    if (flag == 0) next
    split($0, list, ",");
    for (i in list) {
        if (length(list[i]) > 0) {
            gsub("\(.+\)", "", list[i])
            # Let's make sure we are not adding packages that we create
            # here (ie appscale-*).
            if (list[i] ~ /appscale-/) { next }
            packages[count] = list[i]
            count += 1
        }
    }
}

END {
    for (i in packages)
	printf("%s ", packages[i])
}
