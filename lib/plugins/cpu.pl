#!/usr/bin/perl
use strict;
use warnings;

open FH,'mpstat -P ALL|';
my @output=<FH>;
close FH;

foreach (@output){
	if ( $_ =~ /(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*?)\ +(.*)/ ){
		my ($cpu,$usr,$nice,$sys,$iowait,$irq,$soft,$steal,$guest,$idle) = ($3,$4,$5,$6,$7,$8,$9,$10,$11,$12);
		if ( $cpu =~ /all|\d+/){
			printf "%s_usr:%s\n",$cpu,$usr;
			printf "%s_nice:%s\n",$cpu,$nice;
			printf "%s_sys:%s\n",$cpu,$sys;
			printf "%s_iowait:%s\n",$cpu,$iowait;
			printf "%s_irq:%s\n",$cpu,$irq;
			printf "%s_soft:%s\n",$cpu,$soft;
			printf "%s_steal:%s\n",$cpu,$steal;
			printf "%s_guest:%s\n",$cpu,$guest;
			printf "%s_idle:%s\n",$cpu,$idle;
		}
	}
}

print "~==.==~\n";
print @output,"\n";
