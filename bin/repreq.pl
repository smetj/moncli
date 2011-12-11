#!/usr/bin/env perl
# -*- coding: utf-8 -*-
#
#       repreq.pl
#       
#       Copyright 2011 Jelle <development@smetj.net>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#       
#       
use strict;
use warnings;
use Getopt::Long;
use Net::RabbitMQ;
use Sys::Hostname::FQDN qw(fqdn);
use Data::UUID;
use JSON;
use Data::Dumper;


#Set default values
my %options =	(	"service"	=> '',
			"host"		=> '',
			"broker"	=> 'localhost',
			"exchange"	=> 'moncli_report_requests',
			"user"		=> 'guest',
			"password"	=> 'guest',
			"repository"	=> ''
			);

GetOptions (	"service=s" 	=> \$options{service},
		"host=s"	=> \$options{host},
		"broker=s"	=> \$options{broker},
		"exchange=s"	=> \$options{exchange},
		"user=s"	=> \$options{user},
		"password=s"	=> \$options{password},
		"repository=s"	=> \$options{repository}
		);


my $doc = &GetDoc(	$options{repository},
			$options{host},
			$options{service},
			);

my $document = &FillBlancs($doc);
print $document,"\n";

sub FillBlancs(){
	my $doc=shift;
	my $json = decode_json $doc;
	my $ug = new Data::UUID;
	my $uuid = $ug->create();
	$json->{'FQDN'} = fqdn();
	$json->{'UUID'} = $ug->to_string($uuid);
	$json->{'time'} = time();
	$json->{'timezone'} = "CET";	
	return encode_json $json;
}
sub GetDoc(){
	my $repo=shift;
	my $host=shift;
	my $service=shift;
	my @json;
	my $file;
	
	if ( [ -e "$repo/$host/$service" ] ){
		$file = sprintf ( "%s/%s/%s",$repo,$host,$service );
	}
	elsif ( [ -e "$repo/.default/$service" ] ){
		$file = sprintf ( "%s/.default/%s",$repo,$service );
	}
	else{
		$file = "";
	}
	
	if ( $file eq "" ){
		print "No custom nor default report request found.\n";
		exit 3;
	}
	
	open FH, $file;
	@json = <FH>;
	close FH;
	
	my $json = join ( '',@json);
	return $json;
}
