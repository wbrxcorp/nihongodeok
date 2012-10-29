#!/usr/bin/python

if __name__ == '__main__':
    strings = []  # create empty list. in java, List strings = new ArrayList()

    strings.append("abcde")   # adding string to the list.  in java,  strings.add("abcde")
    strings.append("defgh")
    strings.append("ijklm")

    print strings    # ['abcde', 'defgh', 'ijklm']

    # join method concatinates all strings in list using specified delimiter.
    all_strings = "\n\n".join(strings)

    print all_strings
# output is like below
'''
abcde

defgh

ijklm
'''

