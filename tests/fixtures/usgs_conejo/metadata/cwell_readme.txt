

Geologic map and digital database of the Conejo Well 7.5 minute quadrangle, Riverside County, California

By  Robert E. Powell 1

Digital preparation by  Pamela M. Cossette 1


Readme, version 1.0


Open-File Report 01-31
Online version 1.0

http://geopubs.wr.usgs.gov/open-file/01-31



2001




U.S. Department of the Interior
U.S. Geological Survey

Prepared in cooperation with
National Park Service
California Division of Mines and Geology

A product of the Southern California Areal Mapping Project
____________________
1 U.S. Geological Survey, Western Region Earth Surface Processes Team
   W904 Riverside Avenue, Spokane, WA 99201-1087

   For database limitations, see following page

DATABASE LIMITATIONS

Content

This database is preliminary and has not been reviewed for conformity with U.S. Geological Survey editorial standards or with the North American Stratigraphic Code. Any use of trade, product, or firm names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

This database, identified as " Geologic map and digital database of the Conejo Well 7.5 minute quadrangle, Riverside County, California," has been approved for release and publication by the Director of the U.S. Geological Survey. Although this database has been subjected to rigorous review and is substantially complete, the USGS reserves the right to revise the data pursuant to further analysis and review. Furthermore, it is released on the condition that neither the USGS nor the United States Government may be held responsible for any damages resulting from its authorized or unauthorized use.

Spatial Resolution

Use of this digital geologic map should not violate the spatial resolution of the data. The Conejo Well database was developed using digital orthophotograph quarter quadrangles (DOQQs) as a base. DOQQs have a pixel resolution of 1 m and are accurate to a scale of 1:12,000 (1 in = 1,000 ft). Any enlargement beyond 1:12,000 exceeds the spatial resolution of the geologic data and should not be used in lieu of a more detailed site-specific geologic evaluation. Similarly, the digital topographic base map is derived from the U.S. Geological Survey, 1:24,000-scale Conejo Well 7.5 minute quadrangle (provisional edition, 1986); any enlargement beyond 1:24,000 exceeds the spatial resolution of the topographic data. Where the geologic data is used in combination with the topographic data, the resolution of the combined output is limited by the lower resolution of the topographic data. Where this database is used in combination with other data of higher resolution, the resolution of the combined output will be limited by the lower resolution of these data.


	Table of contents

	DATABASE LIMITATIONS ................................................	ii	
		Content .......................................................	ii	
		Spatial Resolution ............................................	ii
	
	INTRODUCTION ........................................................	1

	WHERE TO OBTAIN THE DATABASE  .......................................	2

	DATABASE  INFORMATION AVAILABLE ON THE OPEN-FILE WEBSITE  ...........	3
		Title  ........................................................	3
		Authors  ......................................................	3
		Introduction  .................................................	3
		Browse graphic image  .........................................	3
		Explanatory files  ............................................	3
		Database files  ...............................................	4
		Files for viewing and plotting  ...............................	4

	HOW TO ACCESS THE DATABASE  .........................................	5
		Extracting the database files  ................................	5
		Converting the ARC/INFO interchange/export files  .............	6

	DATABASE CONTENTS AND STRUCTURE  ....................................	7

	HOW TO OBTAIN A PAPER PLOT OF THE GEOLOGIC MAP  .....................	9

	HOW TO ACCESS PORTABLE DOCUMENT FORMAT (.PDF) FILES  ................	10
	
	HOW TO OBTAIN METADATA  .............................................	10

	LIST OF URLs CITED  .................................................	11
		U.S. Geological Survey websites  ..............................	11
		Software websites  ............................................	12



INTRODUCTION

	Open-File Report 01-31 is a digital geologic data set that maps and describes the geology of the Conejo Well 7.5 minute quadrangle, Riverside County, southern California. The Conejo Well database is one of several quadrangle databases that are in preparation for Joshua Tree National Park and vicinity. These quadrangles are a subset of digital quadrangle maps being generated for the Southern California Areal Mapping Project (SCAMP). The SCAMP maps are, in turn, part of the nation-wide digital geologic map coverage being developed by the National Cooperative Geologic Map Project (NCGMP) of the U.S. Geological Survey (USGS).

	The Conejo Well data set consists of a digital geologic map database accompanied by graphics, plot, and explanatory files. The digital database was created using ARCVIEW, version 3.2, and ARC/INFO, version 7.2.1, commercial Geographical Information System (GIS) software designed by Environmental Systems Research Institute (ESRI), Redlands, California (http://www.esri.com). The database includes five ARC/INFO map coverages: geology, dikes, structural data, ornamentation indicating relative movement of fault blocks, and leaders for annotated map unit symbols. It also contains a scanned 1:24,000-scale topographic base and supporting SCAMP symbolsets. PostScript and Portable Document Format files contain a geologic map generated from the database combined with map margin explanatory information created in Adobe Illustrator. Other PDF and ASCII text files contain metadata, a readme document, an explanatory pamphlet, and stand-alone versions of the map-margin Correlation of Map and Database Units (CMU) and Description of Map and Database Units (DMU). As yet, not all of the detailed information about geologic units contained in the map-margin explanation has been entered into the digital database.

	The Conejo Well quadrangle lies between 115° 37' 30" and 115° 45' west longitude and 33° 52' 30" and 33° 45' north latitude. The 7.5 minute quadrangle is subdivided in latitude and longitude by a 2.5-minute tic grid that is marked on the topographic map. For the digital coverages, only the four corner tics that represent the geographic extent of the quadrangle have been generated mathematically in ARC/INFO. Geologic map information entered into ARC/INFO has been spatially registered using the four tics that represent the geographic extent of the quadrangle. Both the geologic database and the topographic base map are represented in polyconic projection referenced to the NAD27 datum. (See metadata for more information about projection.)

In mapping real-world geologic features into the database, geologic contacts, faults, and dikes are represented as lines (arcs), geologic units as polygons and regions, and site-specific structural data as points. ARC/INFO records the spatial coordinates and topology of each feature and links it to a polygon, arc, or point attribute table (.pat, .aat, and .pat, respectively) that uniquely identifies the feature. Feature-attribute tables can be related to other tables that further describe and classify the geologic features. (See metadata and explanatory pamphlet for more information about geologic content of database.)


WHERE TO OBTAIN THE DATABASE

	The Conejo Well 7.5 minute quadrangle data set is available on the USGS Western Region Geologic Publications Server. The data set may be downloaded from the website 

http://geopubs.wr.usgs.gov/open-file/01-31

or by anonymous ftp from the Publications Server:

Server:  geopubs.wr.usgs.gov 
Directory:  /pub/open-file/of01-31.
								
	The Conejo Well geologic map and database can also be accessed through links to the Western Region Geologic Publication Server by any of the following paths:

* http://geology.wr.usgs.gov/wgmt/scamp/scamp.html
This website provides links to SCAMP-related digital geologic mapping in southern California. The site lists new releases by year and title

* http://geopubs.wr.usgs.gov/
This website provides links to USGS Western Region digital geologic maps, including Open-File. The site lists new releases series and number

* http://geology.usgs.gov/open-file/maps.html
This website provides links to all digital USGS Open-File Reports that contain digital map databases. The site lists the Open-File Reports by number along with the title and author(s) of the report

* http://geo-nsdi.er.usgs.gov/cgi-bin/publication?open-file
This website provides links to all digital USGS Open-File Report maps via their metadata files. The site lists the Open-File Reports by number along with the title of the report (see 'How to obtain metadata' below)


DATABASE INFORMATION AVAILABLE ON USGS GEOPUBS SERVER

	On the USGS Western Region Geologic Publications Server (geopubs) website for the Conejo Well geologic map and digital database, information is arranged as follows:

Title
Geologic map and digital database of the Conejo Well 7.5 minute quadrangle, Riverside County, southern California

Authors   
Robert E. Powell
Pamela M. Cossette (digital cartography)

Introduction

Browse-graphic image
Page-sized, non-navigable image of geologic map with marginal explanation

	File name 		File type and description		File size
	===============================================================
	cwell_browse.jpg	JPEG image of geologic map with	~35 KB
				marginal explanation
	
Explanatory files

* Readme tabulates contents of database and describes how to access them. Provided on website in ASCII text and Portable Document formats
* Metadata file contains detailed technical descriptions of structure and content of digital data. Provided on website as parseable text in ASCII format, and as outline in Hypertext Markup Language format. Also available on the USGS Geologic Division Node of the National Geospatial Data Clearinghouse in these two and other formats (see 'How to obtain metadata' below).
* Explanatory pamphlet describes approach used in building database, and discusses purpose, content, and geologic framework of database. Provided on website in ASCII text and Portable Document formats

	File name 		File type and description			File size
	=====================================================================
	cwell_readme.txt	ASCII readme file					 25 KB
	cwell_readme.pdf	PDF readme file					111 KB
	cwell_pamph.txt	ASCII version of explanatory pamphlet	 51 KB
	cwell_pamph.pdf	PDF version of explanatory pamphlet		138 KB
	cwell_met.txt	ASCII metadata file				 74 KB
	cwell_met.html	HTML metadata file				 95 KB


Database files

Database files are packaged as a tarred and gzipped file that bundles and compresses the following information:

* Database files: ASCII-formatted ARC/INFO interchange/export (.e00) file for each ARC/INFO coverage, symbolset, and dictionary. (See 'Database contents and structure' below.)
* ASCII text files for readme, metadata, and explanatory pamphlet

	File name 		File type and description		File size
	===============================================================
	cwell.tar.gz	GZIP compressed 25.2-MB TAR		 5.4 MB
				bundle of all database files			

Files for viewing and plotting

* Gzip-compressed PostScript plot-file for generating paper copy of geologic map with marginal explanation
* Portable Document Format file containing full-sized, navigable graphic image of geologic map with marginal explanation
* Portable Document Format files containing stand-alone versions of Description of Map and Database Units (DMU) and Correlation of Map and Database Units (CMU) from map-margin explanation

	File name 		File type and description			    File size
	=========================================================================
	cwell_map.ps.gz	Gzipped 244-MB PostScript plot file of		8.9 MB
				map with marginal explanation
	cwell_map.pdf	PDF file containing geologic map			5.0 MB
				with marginal explanation
	cwell_cmu.pdf	PDF Correlation of Map & Database Units file	 77 KB
	cwell_dmu.pdf	PDF Description of Map & Database Units file	 70 KB





HOW TO ACCESS THE DATABASE

Extracting the database files

	The Conejo Well database files have been bundled and compressed using tar and gzip utilities. Before attempting to unzip the file after downloading, be sure that the .gz extension is present in the file name.

	Extraction creates the directory cwell/  that contains the database in ARC/INFO interchange (.e00) files, the topographic map in a GEOTIFF file, and the readme, metadata, and explanatory pamphlet in ASCII text files. The database interchange files include five ARC/INFO coverages and supporting symbolsets and dictionaries.

	Tar and uncompress utilities are included in most UNIX systems, and are available free of charge for all systems at various websites:
 
	Gnu Software: http://www.gnu.org/order/ftp.html (UNIX tar and gzip)
		(This web page links to mirror archive sites for Gnu tar and gzip utilities)
	Gnu zip: http://www.gzip.org (UNIX gzip)
	CNET Shareware: http://shareware.cnet.com/ (Macintosh and Windows)
		(Search for 'tar' or 'gzip' for any Macintosh or Windows operating system.)
	WinZip: http://www.winzip.com (Windows gzip)
	USGS Public Domain Software web page:
		http://edcwww.cr.usgs.gov/doc/edchome/ndcdb/public.html (UNIX and Macintosh)
		(Provides links to Washington University at St. Louis Gnu archive for UNIX tar
			and gzip; and to AOL mirror site for Macintosh tar and gzip)
	Internet Literacy's Common Internet File Formats:
		http://www.matisse.net/files/formats.html (Macintosh and Windows tar and gzip)
		(Note: this website has not been maintained since December 1995)


Converting the ARC/INFO interchange/export files

	The ARC interchange/export (.e00) files are converted to ARC coverages using the ARC command IMPORT.

1. Change directories to the cwell/ directory
2. At the UNIX command prompt, launch ARC/INFO by typing "arc"
3. From the ARC command line type:
import <option> <interchange_file> <output>
		(e.g., import auto cwell_geo cwell_geo; repeat for each interchange file)

Consult the ARC/INFO command references manual in ESRI's software documentation for other <option> choices appropriate for importing the interchange files.

	After importing the Conejo Well ARC/INFO interchange files, the cwell/ directory contains five map coverages, two dictionaries, four symbolsets, and three documentation files:


	cwell/
	info/			lines.rel		cwell_readme.txt
	cwell_geo/		points.rel		cwell_met.txt
	cwell_dk/		geoscamp2.lin	cwell_pamph.txt
	cwell_str/		geoscamp2.mrk
	cwell_orn/		scamp2.shd
	cwell_ldr/		geology2.shd
	cwell_topo.tif
	
The info/ directory contains INFO files integral to the database coverages.

	ARC/INFO interchange files can be read by some other Geographic Information Systems, including ARCVIEW (ESRI) and MapInfo (via ArcLink).  Please consult your GIS documentation to see if your system recognizes ARC interchange files and follow the procedure to import them. (NOTE: the graphical symbols contained in the two symbolsets (geoscamp2.lin; geoscamp2.mrk) cannot be read in ARCVIEW.)


DATABASE CONTENTS AND STRUCTURE
	
	This readme section contains tabular listings that summarize the structure and content of the database. Refer to the metadata for a complete technical description of the database structure and content; refer to the explanatory pamphlet for a discussion of the approach used in building the database within the context of its purpose and geologic database.

The database files comprise:

* ARC/INFO coverages
* INFO tables that contain line and point dictionaries
* Symbolsets
* Topographic base map: 500-dpi raster scan of USGS Conejo Well 7.5 minute quadrangle (provisional edition, 1986), registered and rectified to the coverage quadrangle in ARC/INFO and saved as a Georeferenced Tagged Image Format (GEOTIFF) file


	Directory		Directory		Directory or			
	or file name	or file type	file contents	          File size
	=========================================================================
	cwell_geo/		ARC/INFO coverage	Geologic units and contacts
	cwell_dk/		ARC/INFO coverage	Dikes
	cwell_str/		ARC/INFO coverage	Geologic structure			
	cwell_orn/		ARC/INFO coverage	Ornamentation			
	cwell_ldr/		ARC/INFO coverage	Leaders				
	-------------------------------------------------------------------------
	cwell_topo.tif	GEOTIFF 		Raster-scanned topographic map 13.1 MB
	-------------------------------------------------------------------------
	lines.rel		INFO table		Line dictionary			
	points.rel		INFO table		Point dictionary			
	-------------------------------------------------------------------------
	geoscamp2.lin	Lineset		Lines					
	geoscamp2.mrk	Markerset		Points				
	scamp2.shd		Shadeset		Colors				
	geology2.shd	Shadeset		Patterns				


Content of ARC/INFO coverages:

	Coverage: 			
		Feature class:	Feature
			Subclass	attribute table		Contents	
	=========================================================================
	cwell_geo/							Geology
		Arcs			cwell_geo.aat		Contacts and faults
		Polygons		cwell_geo.pat		Geologic map units
		Regions		
			Metunit	cwell_geo.patmetunit	Metamorphic rock units
			Pedunit	cwell_geo.patpedunit	Pedogenic rock units
			Plutunit	cwell_geo.patplutunit	Plutonic rock units
			Sedunit	cwell_geo.patsedunit	Sedimentary rock units
			Veinunit	cwell_geo.patveinunit	Vein rock units
			Volcunit	cwell_geo.patvolcunit	Volcanic and hypabyssal 									rock units
			Hydaltunit	cwell_geo.pathydaltunit	Hydrothermally altered 										rock units
		Annotations			
			Geo (anno.geo)				Geologic map unit labels	
	--------------------------------------------------------------------------
	cwell_dk/							Dikes
		Arcs			cwell_dk.aat		Dikes
	--------------------------------------------------------------------------
	cwell_str/							Structure
		Points		cwell_str.pat		Spatial orientation of 										point data:
									Azimuth and dip of planar 									features
									Azimuth and plunge of 										linear features
		Annotations		
			Value (anno.value)			Dip and plunge values
	--------------------------------------------------------------------------
	cwell_orn/							Ornamentation at points on 									lines
		Points		cwell_orn.pat		Ornamentation 
										Fold axis symbols
										Fault symbols:  slip 											arrows
		Annotations				
			Line (anno.line)				Fault symbols:  U / D
	--------------------------------------------------------------------------
	cwell_ldr/							Leaders for annotated unit 									labels	
		Arcs			cwell_ldr.aat		Leaders	



HOW TO OBTAIN A PAPER PLOT OF THE GEOLOGIC MAP

1.	Download and, using a gzip utility (see 'Extracting the database files' above), uncompress the file cwell_map.ps.gz. The 244-MB file cwell_map.ps is a PostScript plot-file of the geologic map and its explanation. The PostScript file will plot a 1:24.000-scale, full-color geologic map of the Conejo Well quadrangle on its topographic base and accompanied by a map-margin explanation. The plot has a format similar to the U.S. Geological Survey's Miscellaneous Investigations (MF) map series, and is approximately 34 x 44 inches in size. It has been plotted successfully on Hewlett-Packard large-format plotters, models HP650C, HP755CM, and HP2500C using 36 x 48-in paper.

	To add a topographic base to the geologic map, the monochromatic raster-scan file (cwell_topo.tif) and the geologic map coverages were converted to ARC/INFO grids. The grids were then merged to display the topographic and cultural information from the raster scan in gray, with geologic map unit colors filling the intervening areas of the topographic map. The combined map is a digital image in which geologic and topographic lines and points are displayed in their proper geospatial locations, but in which no information other than location is attached to the lines and points.

	The marginal explanation includes a Correlation of Map and Database Units diagram, a Description of Map and Database Units, and a key to line and point symbols. The map margin explanation was created in Adobe Illustrator and imported into ARC/INFO to combine it with the geologic map. 

	The plot files have been prepared using line- and point-symbols and unit colors and patterns located in the following symbolsets:

	geoscamp2.lin	Lines
	geoscamp2.mrk	Points
	scamp2.shd		Colors
	geology2.shd	Patterns

These sets are included in the cwell.tar.gz data package and are available at the Southern California Areal Mapping Project (SCAMP) website

http://geology.wr.usgs.gov/wgmt/scamp/attrib/attribute.html

In addition, the plot files contain specialized geologic-age fonts of the GeoAge font group, which is accessed through geofont.txt and is available from the USGS by anonymous ftp:
		
		Server:  onyx.wr.usgs.gov 
		Directory: /pub/wpg/supplies/geoage/.

2.	Download and plot the 5-MB file cwell_map.pdf, which generates a paper map equal in quality to that of the much larger post-script plot file. Care must be taken to select a page size format that results in 1:24,000-scale map-plot.



HOW TO ACCESS PORTABLE DOCUMENT FORMAT (.PDF) FILES

	The .pdf files are accessed using Adobe Acrobat Reader software, available free of charge from the Adobe web site (http://www.adobe.com).






HOW TO OBTAIN METADATA

	Metadata for the Conejo Well geologic map database are available as part of the National Spatial Data Infrastructure through the USGS Geologic Division Node of the National Geospatial Data Clearinghouse  (http://nsdi.usgs.gov/). Within this site, Open-File Reports are located at

http://geo-nsdi.er.usgs.gov/cgi-bin/publication?open-file

where they are listed by OFR number along with the title. Metadata at this node are viewable in five formats (ASCII as parseable text; HTML outline, HTML as answers to questions, XML, and DIF). Metadata for the Conejo Well database site at this node is located at

http://geo-nsdi.er.usgs.gov/metadata/open-file/00-31/metadata.faq.html

ASCII text and HTML outline versions of the metadata are also available at the Conejo Well website (http://geopubs.wr.usgs.gov/open-file/of01-31) and bundled with database files in the tarred and gzipped file.
 


LIST OF URLs CITED

U.S. Geological Survey websites

	Conejo Well 7.5 minute quadrangle
		Open-File Report: http://geopubs.wr.usgs.gov/open-file/01-31
		Metadata: http://geo-nsdi.er.usgs.gov/metadata/open-file/01-31/metadata.faq.html
		
	Southern California Areal Mapping Project (SCAMP) website 
		GIS attributes: 					http://geology.wr.usgs.gov/wgmt/scamp/attrib/attribute.html
		Databases: http://geology.wr.usgs.gov/wgmt/scamp/

	Western Region Geologic Publication Server
		Open-File Reports:
			http://geopubs.wr.usgs.gov/open-file/of00-  (followed by the OFR number)
		All digital publications
			http://geopubs.wr.usgs.gov/

	U.S. Geological Survey website  (http://geology.usgs.gov)
		Open-File Reports
			Digital maps: http://geology.usgs.gov/open-file/maps.html
			Metadata: http://geo-nsdi.er.usgs.gov/cgi-bin/publication?open-file

		Metadata (USGS Node of the National Geospatial Data Clearinghouse)
			http://nsdi.usgs.gov/

		National Geologic Map Database 
			http://ncgmp.usgs.gov/ngmdbproject/standards/
			http://geology.usgs.gov/dm/



Software websites

	GIS systems
		Environmental Systems Research Institute (ESRI): http://www.esri.com
		MapInfo:  http://www.mapinfo.com 
	
	Compression and tar software
		Gnu Software: http://www.gnu.org/order/ftp.html (UNIX tar and gzip)
			(This web page links to mirror archive sites for Gnu tar and 			gzip utilities)
		Gnu zip: http://www.gzip.org (UNIX gzip)
		CNET Shareware: http://shareware.cnet.com/ (Macintosh and Windows)
			(Search for 'tar' or 'gzip' for any Macintosh or Windows o				operating system.)
		WinZip: http://www.winzip.com (Windows gzip)
		USGS Public Domain Software web page:
			http://edcwww.cr.usgs.gov/doc/edchome/ndcdb/public.html 
			(UNIX, Macintosh)	(Provides links to Washington University at 			St. Louis Gnu archive for UNIX tar and gzip; and to AOL mirror 			site for Macintosh tar and gzip)
		Internet Literacy's Common Internet File Formats:
			http://www.matisse.net/files/formats.html (Macintosh and 				Windows tar and gzip)
			(Note: this website has not been maintained since December 				1995)

	Portable document reader
		Adobe web site: http://www.adobe.com
	

