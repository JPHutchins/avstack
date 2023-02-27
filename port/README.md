# Port to Python

The `avstack.pl` file in this folder has been modified to:

* find object files with extensions `.o` or `.obj`
* require that the path to the `objdump` executable is first argument
* ignore missing `.su` files, e.g. static libraries included that did not generate `.su`

These changes help with regression testing the python version.

Here is the diff of `original/avstack.pl` -> `port/avstack.pl` as of `1cfa548`:
```diff
26c26
< #    ./avstack.pl <object files>
---
> #    ./avstack.pl <objdump path> <object files>
53c53
< my $objdump = "avr-objdump";
---
> my $objdump = $ARGV[0];
68c68
< foreach (@ARGV) {
---
> foreach (@ARGV[1..$#ARGV]) {
109c109
<     if ($objfile =~ /^(.*).o$/) {
---
>     if ($objfile =~ /^(.*).o(bj)?$/) {
112,115c112,122
<       open(SUFILE, "<$sufile") || die "Can't open $sufile";
<       while (<SUFILE>) {
<           $frame_size{"$1\@$objfile"} = $2 + $call_cost
<               if /^.*:([^\t ]+)[ \t]+([0-9]+)/;
---
>       if (-e $sufile) {
>               open(SUFILE, "<$sufile") || die "Can't open $sufile";
>               while (<SUFILE>) {
>                       $frame_size{"$1\@$objfile"} = $2 + $call_cost
>                       if /^.*:([^\t ]+)[ \t]+([0-9]+)/;
>               }
>               close(SUFILE);
>               }
>       else {
>               print("No file: $sufile\n");
>       }
117,118d123
<       close(SUFILE);
<     }
```