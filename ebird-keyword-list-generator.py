#!/opt/homebrew/bin/python3

# parse the eBird_taxonomy.csv file with this format:

# TAXON_ORDER,CATEGORY,SPECIES_CODE,TAXON_CONCEPT_ID,PRIMARY_COM_NAME,SCI_NAME,ORDER,FAMILY,SPECIES_GROUP,REPORT_AS
# 2,species,ostric2,,Common Ostrich,Struthio camelus,Struthioniformes,Struthionidae (Ostriches),Ostriches,


# it has these kinds of entries

    # Spuh:  Genus or identification at broad level, e.g., swan sp. Cygnus sp. 
    # Slash: Identification to Species-pair, e.g., Tundra/Trumpeter Swan Cygnus columbianus/buccinator 
    # Species: e.g., Tundra Swan Cygnus columbianus 
    # ISSF or Identifiable Sub-specific Group: Identifiable subspecies or group of subspecies, e.g., Tundra Swan (Bewick’s) Cygnus columbianus bewickii or Tundra Swan (Whistling) Cygnus columbianus columbianus
    # Hybrid: Hybrid between two species, e.g., Tundra x Trumpeter Swan (hybrid)
    # Intergrade: Hybrid between two ISSF (subspecies or subspecies groups), e.g., Tundra Swan (Whistling x Bewick’s) Cygnus columbianus columbianus x bewickii
    # Domestic: Distinctly-plumaged domesticated varieties that may be free-flying (these do not count on personal lists) e.g., Mallard (Domestic type)
    # Form: Miscellaneous other taxa, including recently-described species yet to be accepted or distinctive forms that are not universally accepted, e.g., Red-tailed Hawk (abieticola), Upland Goose (Bar-breasted)

# and generate a Lightroom Classic Keyword import file like this:

# [IOC World Birds by Family v14.2 2024]
# 	{animals}
# 	{birds}
# 	{Aves}
# 	{Chordata}
# 	{Animalia}
# 	{Eumaniraptora}
# 	{Tetrapoda}
# 	{Avilalae}
# 	{Neornithes}
# 	Ostriches
# 		{Struthionidae}
# 		{Struthioniformes}
# 		{Palaeognathae}
# 		Common Ostrich
# 			{Struthio camelus}
# 		Somali Ostrich
# 			{Struthio molybdophanes}


import csv
import re
from io import StringIO

previous_line = []

print("[eBird taxonomy v2024]")

with open("eBird_taxonomy_v2024.csv", "r") as file:
	# use the CSV reader so that we observe quoted strings
	reader = csv.reader(file)
	for line in reader:
		# special case for the first line of the file
		if previous_line == []:
			previous_line = line
			continue

		# we could isnert orders into the hierarchy, but we opt not to
		# if (line[6] != previous_line[6]):
		# 	print("	" + line[6])

		# print the common name and scientific name for all the kinds of entries except "spuh"
		if (line[1] == "species"):
			# print the family if its not the same as the last one
			# the format for family names is "Struthionidae (Ostriches)", use a regular expression to extract all the strings inside parentheses
			common_family_name_array = re.findall(r"\((.*?)\)", line[7])
			# take the first string inside parentheses and get rid of commas that Lightroom Classic does not permit
			common_family_name = common_family_name_array[0].replace(",", "")

			if (line[7] != previous_line[7]):
				print("	" + common_family_name)

			print("		" + line[4])
			print("			{" + line[5] + "}")

		previous_line = line