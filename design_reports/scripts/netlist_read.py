#!/usr/bin/env python3

# AFC Pinout helper script
# Copyright (C) 2020 CNPEM
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# This scripts generates CSV that make it easy to analyse pinout data
# for the FPGA and the LPC ICs in the AFC. It also allows for quick
# checks on the RTM connector pinout, comparing it to net names
# connected to it. It also automatically generates assembly option
# tables for the MGTs, following the different options and setting
# which capacitors enable them.
#
# The script expects a project-wide Cadnetix Netlist file as exported
# by Altium. Please remember compiling the project before generating
# the netlist!
#
# The CSVs are supposed to be used as inputs for the ODS table
# avilable in the project to correlate them with IC pin functions and
# connectors standards

import itertools
import csv

class Netlist:
    def __init__(self, file):
        self.nodes = {}
        with open(file, 'r+', encoding="latin-1") as netlist:
            for line in netlist:
                if "NODENAME" in line:
                    break

            for line in netlist:
                if  "EOS" in line:
                    break
                if "NODENAME" in line:
                    nodename = line.split()[1]
                    self.nodes[nodename]=[]

                    line2 = next(netlist)
                    connection = line2.split()
                    for ic, pin in zip(connection[0::2], connection[1::2]):
                        self.nodes[nodename].append((ic,pin))


    def write_part_nets(self, file, part):
        with open(file,'w',newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter =';')
            for node, connections in self.nodes.items():
                for connection in connections:
                    if connection[0] in part:
                        csvwriter.writerow((connection[0],connection[1],node))

    def get_node_from_port(self, port):
        for node, ports in self.nodes.items():
            if port in ports:
                return node

    #given a two-pin part and its pin, returns the node in the other pin in a netlist
    def cross_twopin(self, port):
        (part, pin) = port

        if pin == '1':
            new_port = (part,'2')
        else:
            new_port = (part,'1')

        new_node = self.get_node_from_port(new_port)
        return(new_port,new_node)


    #Follow all resistors and capacitors to follow a signal from IC to IC or Connector
    def follow_asm_opt(self, start_port, start_node=None, path=[]):

        if start_node == None:
            start_node = self.get_node_from_port(start_port)
            if start_node == None:
                return [start_port,"end"]

        path = path + [(start_port,start_node)]

        paths = []

        #scan all pins in this node
        for port in self.nodes[start_node]:

            #prevent coming back
            if (port == start_port):
                continue

            (part,pin) = port

            # As the end of the graph is not known beforehand, we walk until we find something which is not 2-pi
            if is_twopin(part):
                (next_port,node) = self.cross_twopin(port)

                #depth first search. Not the most efficient, but more than enough for any reasonable and most unreasonable circuits
                new_paths = self.follow_asm_opt(next_port,node,path)
                for new_path in new_paths:
                    paths.append(new_path)

            else:
                path = path + [(port,"end")]
                paths.append(path)

        return paths


#check if a part is two-pin passive (L, C or R) by name standard
def is_twopin(part):
    if(part[0] in ('R','L','C')):
        return part[1:].isnumeric()
    else:
        return False;

# This function follows all the possible paths for a given signal and writes it to a CSV. Do not use it in power rails or pulled-up signals, as it will follow all nodes on that rail
def write_mgt_options(netlist):
    output_file = "mgt_options.csv"

    with open('afc_mgt_pins.csv') as in_file:
        csv_reader = csv.reader(in_file, delimiter=',')
        mgt_ports = []
        for row in csv_reader:
            mgt_ports.append(('IC2',row[0]))

    mounting_options=[]
    for port in mgt_ports:
        mounting_options.append(netlist.follow_asm_opt(port))

    try:
        with open(output_file,"w") as out_file:
            csv_writer = csv.writer(out_file,delimiter=';')
            for mgt_port in mounting_options:
                for option in mgt_port:
                    line = []
                    for ((part,pin),node)in option:
                        line=line+[part]+[pin]+[node]
                    csv_writer.writerow(line)
    except ValueError:
        print("ValueError, option: " + str(option))

def write_rtm_resistors(netlist):
    output_file =  "rtm_resistor.csv"
    parts = ("R215","R249","R251","R253","R385","R386","R388","R390")
    netlist.write_part_nets(output_file, parts)

def write_rtm_connectors(netlist):
    output_file =  "rtm_connector.csv"
    parts = ("J1","J2")
    netlist.write_part_nets(output_file, parts)

def write_lpc_connections(netlist):
    output_file = "lpc_connection.csv"
    parts = "IC1"
    netlist.write_part_nets(output_file,parts)

def write_fpga_connections(netlist):
    output_file = "fpga_connection.csv"
    parts = "IC2"
    netlist.write_part_nets(output_file,parts)


input_file = "AMC_FMC_Carrier.NET"
afc = Netlist(input_file)
write_fpga_connections(afc)
write_rtm_connectors(afc)
write_lpc_connections(afc)
write_rtm_resistors(afc)
write_mgt_options(afc)
