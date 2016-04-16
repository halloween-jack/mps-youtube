import math
import copy
import random

import pafy

from . import g, c
from .util import getxy, fmt_time, uea_pad, yt_datetime

# In the future, this could support more advanced features
class Content:
    pass


class PaginatedContent(Content):
    def getPage(self, page):
        raise NotImplementedError

    def numPages(self):
        raise NotImplementedError


class LineContent(PaginatedContent):
    def getPage(self, page):
        max_results = getxy().max_results
        s = page * max_results
        e = (page + 1) * max_results
        return self.get_text(s, e)

    def numPages(self):
        return math.ceil(self.get_count()/getxy().max_results)

    def get_text(self, s, e):
        raise NotImplementedError

    def get_count(self):
        raise NotImplementedError


class StringContent(LineContent):
    def __init__(self, string):
        self._lines = string.splitlines()

    def get_text(self, s, e):
        return '\n'.join(self._lines[s:e])

    def get_count(self):
        width = getxy().width
        count = sum(len(i) // width + 1 for i in self._lines)
        return count


def page_msg(page=0):
    """ Format information about currently displayed page to a string. """
    if isinstance(g.content, PaginatedContent):
        page_count = g.content.numPages()
    else:
        page_count = math.ceil(g.result_count/getxy().max_results)

    if page_count > 1:
        pagemsg = "{}{}/{}{}"
        #start_index = max_results * g.current_page
        return pagemsg.format('<' if page > 0 else '[',
                              "%s%s%s" % (c.y, page+1, c.w),
                              page_count,
                              '>' if page + 1 < page_count else ']')
    return None


def generate_songlist_display(song=False, zeromsg=None):
    """ Generate list of choices from a song list."""
    # pylint: disable=R0914
    if g.browse_mode == "ytpl":
        return generate_playlist_display()

    max_results = getxy().max_results

    if not g.model:
        g.message = zeromsg or "Enter /search-term to search or [h]elp"
        return logo(c.g) + "\n\n"
    g.rprompt = page_msg(g.current_page)

    have_meta = all(x.ytid in g.meta for x in g.model)
    user_columns = _get_user_columns() if have_meta else []
    maxlength = max(x.length for x in g.model)
    lengthsize = 8 if maxlength > 35999 else 7
    lengthsize = 5 if maxlength < 6000 else lengthsize
    reserved = 9 + lengthsize + len(user_columns)
    cw = getxy().width
    cw -= 1
    title_size = cw - sum(1 + x['size'] for x in user_columns) - reserved
    before = [{"name": "idx", "size": 3, "heading": "Num"},
              {"name": "title", "size": title_size, "heading": "Title"}]
    after = [{"name": "length", "size": lengthsize, "heading": "Time"}]
    columns = before + user_columns + after

    for n, column in enumerate(columns):
        column['idx'] = n
        column['sign'] = "-" if not column['name'] == "length" else ""

    fmt = ["%{}{}s  ".format(x['sign'], x['size']) for x in columns]
    fmtrow = fmt[0:1] + ["%s  "] + fmt[2:]
    fmt, fmtrow = "".join(fmt).strip(), "".join(fmtrow).strip()
    titles = tuple([x['heading'][:x['size']] for x in columns])
    hrow = c.ul + fmt % titles + c.w
    out = "\n" + hrow + "\n"

    for n, x in enumerate(g.model[:max_results]):
        col = (c.r if n % 2 == 0 else c.p) if not song else c.b
        details = {'title': x.title, "length": fmt_time(x.length)}
        details = copy.copy(g.meta[x.ytid]) if have_meta else details
        otitle = details['title']
        details['idx'] = "%2d" % (n + 1)
        details['title'] = uea_pad(columns[1]['size'], otitle)
        cat = details.get('category') or '-'
        details['category'] = pafy.get_categoryname(cat)
        data = []

        for z in columns:
            fieldsize, field = z['size'], z['name']
            if len(details[field]) > fieldsize:
                details[field] = details[field][:fieldsize]

            data.append(details[field])

        line = fmtrow % tuple(data)
        col = col if not song or song != g.model[n] else c.p
        line = col + line + c.w
        out += line + "\n"

    return out + "\n" * (5 - len(g.model)) if not song else out


def generate_playlist_display():
    """ Generate list of playlists. """
    if not g.ytpls:
        g.message = c.r + "No playlists found!"
        return logo(c.g) + "\n\n"
    g.rprompt = page_msg(g.current_page)

    cw = getxy().width
    fmtrow = "%s%-5s %s %-12s %-8s  %-2s%s\n"
    fmthd = "%s%-5s %-{}s %-12s %-9s %-5s%s\n".format(cw - 36)
    head = (c.ul, "Item", "Playlist", "Author", "Updated", "Count", c.w)
    out = "\n" + fmthd % head

    for n, x in enumerate(g.ytpls):
        col = (c.g if n % 2 == 0 else c.w)
        length = x.get('size') or "?"
        length = "%4s" % length
        title = x.get('title') or "unknown"
        author = x.get('author') or "unknown"
        updated = yt_datetime(x.get('updated'))[1]
        title = uea_pad(cw - 36, title)
        out += (fmtrow % (col, str(n + 1), title, author[:12], updated, str(length), c.w))

    return out + "\n" * (5 - len(g.ytpls))


def _get_user_columns():
    """ Get columns from user config, return dict. """
    total_size = 0
    user_columns = Config.COLUMNS.get
    user_columns = user_columns.replace(",", " ").split()

    defaults = {"views": dict(name="viewCount", size=4, heading="View"),
                "rating": dict(name="rating", size=4, heading="Rtng"),
                "comments": dict(name="commentCount", size=4, heading="Comm"),
                "date": dict(name="uploaded", size=8, heading="Date"),
                "user": dict(name="uploaderName", size=10, heading="User"),
                "likes": dict(name="likes", size=4, heading="Like"),
                "dislikes": dict(name="dislikes", size=4, heading="Dslk"),
                "category": dict(name="category", size=8, heading="Category")}

    ret = []
    for column in user_columns:
        namesize = column.split(":")
        name = namesize[0]

        if name in defaults:
            z = defaults[name]
            nm, sz, hd = z['name'], z['size'], z['heading']

            if len(namesize) == 2 and namesize[1].isdigit():
                sz = int(namesize[1])

            total_size += sz
            cw = getxy().width
            if total_size < cw - 18:
                ret.append(dict(name=nm, size=sz, heading=hd))

    return ret


def logo(col=None, version=""):
    """ Return text logo. """
    col = col if col else random.choice((c.g, c.r, c.y, c.b, c.p, c.w))
    logo_txt = r"""                                             _         _
 _ __ ___  _ __  ___       _   _  ___  _   _| |_ _   _| |__   ___
| '_ ` _ \| '_ \/ __|_____| | | |/ _ \| | | | __| | | | '_ \ / _ \
| | | | | | |_) \__ \_____| |_| | (_) | |_| | |_| |_| | |_) |  __/
|_| |_| |_| .__/|___/      \__, |\___/ \__,_|\__|\__,_|_.__/ \___|
          |_|              |___/"""
    version = " v" + version if version else ""
    logo_txt = col + logo_txt + c.w + version
    lines = logo_txt.split("\n")
    length = max(len(x) for x in lines)
    x, y, _ = getxy()
    indent = (x - length - 1) // 2
    newlines = (y - 12) // 2
    indent, newlines = (0 if x < 0 else x for x in (indent, newlines))
    lines = [" " * indent + l for l in lines]
    logo_txt = "\n".join(lines) + "\n" * newlines
    return "" if g.debug_mode else logo_txt
