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
from argh import arg, ArghParser
from datetime import datetime
from lxml import etree
from urllib2 import urlopen
from coordinates import ETRSTM35FINxy_to_WGS84lalo
import logging
import sys

KML_URL = 'http://www.opengis.net/kml/2.2'
KML_NS = '{' + KML_URL + '}'
URL_INFO = 'http://www.karttarekisteri.fi/karttarekisteri2/www_visualisointi/tiedot.php?t={id}'
URL_KML = 'http://www.karttarekisteri.fi/karttarekisteri2/ssl_kml_lataus_testi.php?laji={type}'

MAP_TYPES = [
    # numeric id, filename/cmdline option, human readable name
    (1, 'orienteering', 'Orienteering Map'),
    (2, 'sprint', 'Sprint Orienteering Map'),
    (3, 'skio', 'Ski-Orienteering Map'),
    (4, 'mtbo', 'MTB-O Map'),
    (5, 'trailo', 'Trail Orienteering Map'),
    (6, 'opetus', 'Opetuskartta'),
    (7, 'embargoed', 'Embargoed Area'),
]
MAP_TYPE_DICT = dict((x[1], x[0]) for x in MAP_TYPES)
MAP_TYPE_NAMES = [x[1] for x in MAP_TYPES]


def convert_coordinates(coordstr):
    """
    Convert ETRS-TM35FIN formatted <coordinates> tag to WGS84 lat/lon
    Also sets the (invalid) altitude to 0 and adds possibly
    missing last connecting lat/lon point.
    """
    ret = []
    for line in coordstr.strip().splitlines():
        values = [x.strip() for x in line.split(',')]
        convsrc = {'E': int(values[0]), 'N': int(values[1])}
        convtgt = ETRSTM35FINxy_to_WGS84lalo(convsrc)
        altitude = 0
        ret.append("%.6f,%.6f,%s" % (convtgt['Lo'], convtgt['La'], altitude))
    if ret:
        # connect the last line in the polygon (ff not already there)
        if ret[0] != ret[-1]:
            ret.append(ret[0])
    return " ".join(ret)


def convert_kml(stream_in, stream_out, default_map_type="Orienteering Map"):
    """ Converts broken SSL KML """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(stream_in, parser)
    for elem in tree.iterfind('.//' + KML_NS + 'Placemark'):
        logging.debug("Found <Placemark> %s", elem)
        map_id = None
        map_type = ""

        # determine map type from <styleUrl>#transRedPoly</styleUrl>
        styleurl = elem.find(KML_NS + 'styleUrl')
        if styleurl is not None:
            if styleurl.text == '#transRedPoly':
                map_type = "Embargoed Area"
            elif styleurl.text == '#transGreenPoly':
                map_type = default_map_type
            logging.debug("Map type: %s", map_type)

        # <name> is a direct child of placemark
        name = elem.find(KML_NS + "name")
        if name is not None:
            map_id = name.text.strip()
            logging.debug("Map ID %s", map_id)
            name.text = ("%s %s" % (map_type, map_id)).strip()

        # add URL to description, should show up nicely in Google Earth and others
        description = elem.find(KML_NS + 'description')
        if description is not None and map_id:
            logging.debug("Adding URL to description %s", description)
            if description.text:
                description.text += "\n"
            description.text += URL_INFO.format(id=map_id)

        # others live inside <Polygon> (could revert back to .find()...)
        polygon = elem.find(KML_NS + 'Polygon')
        if polygon is not None:
            # remove altitudeMode as the altitude data is invalid anyway
            # this makes it implicitly "clampToGround"
            altmode = polygon.find(KML_NS + 'altitudeMode')
            if altmode is not None:
                polygon.remove(altmode)

            # convert coordinates tag (deeper inside the structure, not direct child of polygon)
            # this part might include invalid data; such polygons are removed from the document.
            # TODO: remove whole Placemark?
            try:
                for coord in polygon.iterfind('.//' + KML_NS + 'coordinates'):
                    logging.debug("Converting <coordinates> %s", coord)
                    coord.text = convert_coordinates(coord.text)
            except StandardError:
                logging.exception("Invalid coordinate data for map %s: %r", map_id, coord.text)
                polygon.getparent().remove(polygon)

    tree.write(stream_out, encoding='utf-8', pretty_print=True)


def convert(dummy_args):
    """ Convert stdin to stdout """
    logging.basicConfig(level=logging.INFO)
    convert_kml(sys.stdin, sys.stdout)


@arg('type', default="all", nargs='*', help='Map type(s) to download', choices=MAP_TYPE_NAMES + ["all"])
def download(args):
    """ Download given map lists """
    logging.basicConfig(level=logging.INFO)
    if isinstance(args.type, basestring):
        args.type = [args.type]
    if "all" in args.type:
        logging.info("Downloading all map types")
        args.type = MAP_TYPE_NAMES
    tstamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for map_type in args.type:
        fname = "ssl-%s-%s.kml" % (map_type, tstamp)
        map_type_id = MAP_TYPE_DICT[map_type]
        dl_url = URL_KML.format(type=map_type_id)
        logging.info("Downloading and converting %s from %s to %s", map_type, dl_url, fname)
        with open(fname, 'wb') as kml_out:
            convert_kml(urlopen(dl_url), kml_out, default_map_type=map_type.title() + " Map")
        logging.info("%s created", fname)
    logging.info("All done.")


def main(argv=None):
    """ Main method / entry point """
    if argv is None:
        argv = sys.argv[1:]
    description = "SSL Karttarekisteri KML tool"
    parser = ArghParser(description=description)
    parser.add_commands([convert, download])
    parser.dispatch(argv=argv)

if __name__ == '__main__':
    main()
