"""
Script for converting SSL Karttarekisteri KML files to more usable format

What it does:
* converts coordinates from ETRS-TM35fin to normal (WGS84) Lat/Lon coordinates
* adds URL to <description>
* removes <altitudeMode> tag to make the polygon fully visible (clamped to ground)
* adds map type to <name>


Uses coordinates.py from http://olammi.iki.fi/sw/fetch_map/ for the coordinate conversion.
Note: if licensing becomes an issue, coord conversion could be done with some other lib or directly here

Copyright (c) 2013 Jyrki Muukkonen <jvtm@kruu.org>

This work is free. You can redistribute it and/or modify it under the
terms of the Do What The Fuck You Want To Public License, Version 2,
as published by Sam Hocevar. See the COPYING file for more details.
"""
from lxml import etree
from coordinates import ETRSTM35FINxy_to_WGS84lalo
import logging
import sys

KML_URL = 'http://www.opengis.net/kml/2.2'
KML_NS = '{' + KML_URL + '}'
HTTP_URL = 'http://www.karttarekisteri.fi/karttarekisteri2/www_visualisointi/tiedot.php?t={id}'


def convert_coordinates(coordstr):
    ret = []
    for line in coordstr.strip().splitlines():
        values = [x.strip() for x in line.split(',')]
        convsrc = {'E': int(values[0]), 'N': int(values[1])}
        convtgt = ETRSTM35FINxy_to_WGS84lalo(convsrc)
        # not sure what the third value is...
        #ret.append("%.6f,%.6f,%s" % (convtgt['Lo'], convtgt['La'], values[2]))
        ret.append("%.6f,%.6f,%s" % (convtgt['Lo'], convtgt['La'], 0))
    if ret:
        # connect the last line in the polygon (ff not already there)
        if ret[0] != ret[-1]:
            ret.append(ret[0])
    return " ".join(ret)


def convert_kml(stream_in, stream_out):
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(stream_in, parser)
    for elem in tree.iterfind('.//' + KML_NS + 'Placemark'):
        logging.info("Found <Placemark> %s", elem)
        map_id = None
        map_type = ""

        # determine map type from <styleUrl>#transRedPoly</styleUrl>
        styleurl = elem.find(KML_NS + 'styleUrl')
        if styleurl is not None:
            if styleurl.text == '#transRedPoly':
                map_type = "Harjoituskielto"
            elif styleurl.text == '#transGreenPoly':
                map_type = "Suunnistuskartta"
            logging.info("Map type: %s", map_type)

        # <name> is a direct child of placemark
        name = elem.find(KML_NS + "name")
        if name is not None:
            logging.info("Map ID %s", map_id)
            map_id = name.text.strip()
            name.text = ("%s %s" % (map_type, map_id)).strip()

        # add URL to description, should show up nicely in Google Earth and others
        description = elem.find(KML_NS + 'description')
        if description is not None and map_id:
            logging.info("Adding URL to description %s", description)
            if description.text:
                description.text += "\n"
            description.text += HTTP_URL.format(id=map_id)

        # others live inside <Polygon> (could revert back to .find()...)
        polygon = elem.find(KML_NS + 'Polygon')
        if polygon is not None:
            # remove altitudeMode as the altitude data is invalid anyway
            # this makes it implicitly "clampToGround"
            altmode = polygon.find(KML_NS + 'altitudeMode')
            if altmode is not None:
                polygon.remove(altmode)

            # convert coordinates tag (deeper inside the structure)
            #coord = polygon.find(KML_NS + 'coordinates')
            for coord in polygon.iterfind('.//' + KML_NS + 'coordinates'):
                logging.info("Converting <coordinates> %s", coord)
                coord.text = convert_coordinates(coord.text)

    tree.write(stream_out, encoding='utf-8', pretty_print=True)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    logging.basicConfig(level=logging.INFO)
    convert_kml(sys.stdin, sys.stdout)

if __name__ == '__main__':
    main()
