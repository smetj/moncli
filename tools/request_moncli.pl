#!/usr/bin/perl
# -*- coding: utf-8 -*-
#
#       check_moncli
#       
#       Copyright 2011 Jelle Smet <web@smetj.net>
#       
#       This file is part of check_moncli.
#       
#           Check_moncli is free software: you can redistribute it and/or modify
#           it under the terms of the GNU General Public License as published by
#           the Free Software Foundation, either version 3 of the License, or
#           (at your option) any later version.
#       
#           Check_moncli is distributed in the hope that it will be useful,
#           but WITHOUT ANY WARRANTY; without even the implied warranty of
#           MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#           GNU General Public License for more details.
#       
#           You should have received a copy of the GNU General Public License
#           along with check_moncli.  If not, see <http://www.gnu.org/licenses/>.
use strict;
#use warnings;
use Getopt::Long;
use JSON;
use URI::Escape;
use HTTP::Request::Common qw(POST);
use LWP::UserAgent;
use UUID::Tiny;
use POSIX;
use Sys::Hostname::FQDN qw (fqdn);
my $version="0.1";
############################################################################################################
########### Begin user definable variables.
############################################################################################################
my $exit_on_error=3;
############################################################################################################
########### End user definable variables.
############################################################################################################
my $now = localtime; 

#Set some default options
my %options = ( 'username'			=> '',
		'password'			=> '',
		'timeout'			=> '10',
		'pluginTimeout'			=> '30',
		'cycle'				=> '300',
		'reason'			=> 'New request',
		'subject'			=> '',
		'destination'			=> '',
		'message'			=> '',
		'target'			=> '',
		'plugin'			=> '',
		'pluginTimeout'			=> '60',
		'pluginParameters'		=> '',
		'evaluators'			=> '',
		'nagiosType'			=> 'service',
		'tags'				=> '[\"request_moncli\"]',
		'debug'				=> ''
		);
				
GetOptions (	"url:s"			=> \$options{url},
		"username:s"		=> \$options{username},
		"password:s"		=> \$options{password},
		"timeout:i"		=> \$options{timeout},
		"reason:s"		=> \$options{reason},
		"cycle:s"		=> \$options{cycle},
		"subject:s"		=> \$options{subject},
		"destination:s"		=> \$options{destination},
		"message:s"		=> \$options{message},
		"target:s"		=> \$options{target},
		"plugin:s"		=> \$options{plugin},
		"pluginTimeout:i"	=> \$options{pluginTimeout},
		"pluginParameters:s"	=> \$options{pluginParameters},
		"evaluators:s"		=> \$options{evaluators},
		"nagiosType:s"		=> \$options{nagiosType},
		"help"			=> \$options{help},
		"tags"			=> \$options{tags},
		"debug:s"		=> \$options{debug}
		);

#If help defined show and exit
if ( defined $options{help} ){
	&help;
}				

#Verify the received options
my $mode = shift;
chomp($mode);

if ( $mode eq "system" ){
	$options{'type'} = "systemRequest";
}
elsif ( $mode eq "report" ){
	$options{'type'} = "reportRequest";
}
else{
	&help("Request mode should be either system or report",$exit_on_error);
}

&verify_options(\%options,$mode);

if ($options{'nagiosType'} eq 'host'){
	$options{'weight_map'} ='nagios:host';
	$options{'format'} = 'nagios:host';
}
else{
	$options{'weight_map'} ='nagios:service';
	$options{'format'} = 'nagios:service';
}



#Complete options
$options{'UUID'} = create_UUID_as_string(UUID_V4);
$options{'timezone'} = strftime("%Z", localtime());
$options{'time'} = time();
$options{'FQDN'} = fqdn();

#Construct json payload
my $payload = &construct_payload(\%options);
if ( $options{'debug'} ne '' ){
	open FH,">>$options{debug}/".$options{subject}.'.'.$options{target};
	print FH "======================================================\n";
	print FH $payload;
	print FH "\n======================================================\n\n";
	close FH;
}

#Submit to moncli
my $ua = LWP::UserAgent->new;
my $req = POST $options{url},[ username => $options{username}, password => $options{password}, input=>$payload];
my $response = $ua->request($req);

#Produce output
if ($response->is_success) {
	printf "%s: Report request %s submitted to %s. Waiting for incoming results.\n",(strftime "%a %b %e %H:%M:%S %Y", localtime),$options{'UUID'},$options{'target'};
	exit 3;
	}
else{
     print "Error submitting command to host :".$response->status_line,"\n";
     exit $exit_on_error;
	}

sub construct_payload(){
	my $options_ref=shift;
	my %data = %$options_ref;
	eval{$data{destination}	= from_json($options_ref->{destination})} or &help("Error in --destination parameter",$exit_on_error);
	eval{$data{evaluators}	= from_json($options_ref->{evaluators})} or &help("Error in --evaluators parameter",$exit_on_error);
	delete $data{username};
	delete $data{password};
	delete $data{url};
	delete $data{help};
	delete $data{timeout};
	delete $data{nagiosType};
	delete $data{debug};
	return encode_json(\%data);
	
};
sub verify_options(){
		my $options_ref=shift;
		my $mode=shift;
		if ( not exists $options_ref->{url} || $options_ref->{url} !~ /^http(|s):\/\// ){
			&help("Option --url is mandatory or it needs to have 'http(s)://' format.",$exit_on_error);
		}
		if (not defined $options_ref->{destination}){
			&help("Parameter --destination is mandatory in data mode.",$exit_on_error);
		}
		if (not defined $options_ref->{evaluators}){
			&help("Parameter --evaluators is mandatory in data mode.",$exit_on_error);
		};
		if ($options_ref->{nagiosType} ne 'host' && $options_ref->{nagiosType} ne 'service'){
			&help("Parameter --type should be either 'host' or 'service'",$exit_on_error);
		};
}
sub help(){
	my $message=shift || '';
	my $exitcode=shift || 0;
	print <<HELP
request_moncli $version\t\t\t\tweb\@smetj.net

request_moncli is a client which facilitates communication between Nagios based monitoring frameworks and Moncli.

USAGE: 

check_moncli command --url address [--username value] [--password value] --name value --type value --hostname value --servicename value --plugin value --message_template value --evaluators value --destination value [--perfdata_template value] [--schedule value] [--plugin_timeout value] [--prev_exit_code value] [--prev_message value]

Commands:
		report			Sends a report request to Moncli.
		system			Sends a system request to Moncli (not implemented yet).

Parameters:
		--url			The complete url (including port) on which the moncli software is listing.
		--username		The username required to authenticate to Moncli if required. (optional)
		--password		The password required to authenticate to Moncli if required. (optional)

Data mode parameters:

		--timeout 		Timeout connecting to Moncli.
		--target 		The name of of the Host object in Nagios.
		--subject 		The name of the service in Nagios.
		--plugin 		The name of the plugin script to execute (located in the --repo directory).
		--destination 		The destination (in json format) to which the the report has to go to.
		--evaluators 		The evaluator definitions in json format.
		--nagiosType		Can be either "service" or "host".  Determines the result type for Nagios.
		--message 		The message appearing in Nagios containing placeholders with the names of your evaluators.
		--cycle 		Determines the amount of seconds Moncli reschedules the check.  0 doesn't schedule and will erase a previously scheduled check.
		--debug			Writes the report request in JSON format to the /tmp/ directory with filename --target + --subject


Command mode parameters:
		--to be defined

Example:
The command has been spread over multiple lines for clarity.

request_moncli.pl report \
	--url http://127.0.0.1:6555 \
	--username default \
	--password changeme \
	--timeout 60 \
	--target 'sandbox' \
	--subject 'Memory' \
	--plugin 'memory.py' \
	--destination '{	"type":"nscaweb", 
				"locations":["http://localhost:5668/queue"],
				"username":"default", 
				"password":"changeme"}' \
	--evaluators '{	"actual": 
				{"thresholds":{"warning":"\@0:11","critical":"\@10:100"}, 
				"evaluator":"fm:100-(((memfree+buffers+cached)/memtotal)*100)","metric":"%"}, 
			"swap":
				{"thresholds":{"warning":"\@0:11","critical":"\@10:100"}, 
				"evaluator":"fm:100-((swapfree/swaptotal)*100)","metric":"%"}, 
			"physical": 
				{"thresholds":{"warning":"\@0:11","critical":"\@10:100"}, 
				"evaluator":"fm:100-((memfree/memtotal)*100)","metric":"%"} 
			}' \
	--nagiosType service \
	--message 'Physical #physical % * Actual #actual % * Swap #swap %' \
	--cycle '60' \
	--debug '/tmp'


For a detailed explanation please visit: http://www.smetj.net/wiki/Moncli_integration_nagios#request_moncli.pl

$message

HELP
;
exit $exitcode;
}
