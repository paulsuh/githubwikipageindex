import fileinput
import re
from os import rename, scandir
from os.path import splitext


"""
Generates page index for a wiki
"""

# excludes files and folders that start with a dot, like .git or .DS_Store
# also excludes _Sidebar.md, _Footer.md, and Home.md
file_exclusion_re: re.Pattern = re.compile(
    r"^\..*$|^_Sidebar\.md$|^_Footer.md$|Home.md"
)

# translation tables for str.translate
dash_to_space = str.maketrans("-", " ")
underscore_to_space = str.maketrans("_", " ")

start_marker = "<!--start Page Index-->\n"
end_marker = "<!--end Page Index-->\n"


def insert_page_index() -> None:
    """
    Generate the Page Index and place the text into the Home.md file.
    If the HTML comments <!--start Page Index--> and <!--end Page Index-->
    exist then the Page Index will be inserted between them. Otherwise, the
    Page Index will be placed at the start of the file and the comments will
    be added. Text above the start marker and text below the end marker will
    be preserved.
    """

    rename("Home.md", "Home.md.old")
    with open("Home.md", "w") as new_home_md:
        with open("Home.md.old", "r") as old_home_md:

            # Read and dump out text before the Page Index
            while one_line := old_home_md.readline():
                if one_line == start_marker:
                    # We reached the top of the old Page Index
                    break
                else:
                    # We haven't reached the top of the old Page Index yet so
                    # transfer the old content to the new file.
                    new_home_md.write(one_line)

            if len(one_line) == 0:
                # reached EOF without finding an existing Page Index
                # Put the Page Index at the beginning of the file, then
                # rewind and put the rest of the old home page's content
                # after that.
                # This is slightly inefficient, but good enough for this purpose
                new_home_md.seek(0)
                new_home_md.write(generate_page_index())
                old_home_md.seek(0)
                for existing_line in old_home_md:
                    new_home_md.write(existing_line)
                return

            # We found the old Page Index, so skip lines until the end of the old Page Index
            while one_line := old_home_md.readline():
                if one_line == end_marker:
                    break

            # Either we found the old Page Index and skipped to the bottom of it,
            # or we never found the bottom marker and skipped all of the rest
            # of the file.
            # In either case write the new Page Index
            new_home_md.write(generate_page_index())

            # Read and dump out text after the Page Index
            while one_line := old_home_md.readline():
                new_home_md.write(one_line)


def generate_page_index() -> str:
    """
    Scan the wiki pages and produce a Page Index.

    :return: Markdown-formatted Page Index
    """
    result: str = f"{start_marker}\n# Page Index\n\n"
    tag_tree: dict = {
        "untagged": set()
    }

    # get the list of files
    files_in_dir = scandir()
    files_to_scan = [
        f.name
        for f in files_in_dir
        if f.is_file() and not file_exclusion_re.match(f.name)
    ]

    # openhook is to handle files with screwed up Unicode encoding, otherwise fileinput
    # crashes
    with fileinput.input(files_to_scan,
                         openhook=lambda filename, mode: open(filename, mode, errors="replace")) as f:
        for one_line in f:
            fn = fileinput.filename()

            # assume the page is untagged
            tag_tree["untagged"].add(fn)
            if len(tags_list := _scan_line_for_tags(one_line)) > 0:
                # tag found, remove the page from the list of completely untagged files
                # and add it to one of the tag entries
                tag_tree["untagged"].discard(fn)
                for one_tag in tags_list:
                    _add_page_to_tag_dict(fn, one_tag, tag_tree)
                fileinput.nextfile()

    result += _render_tag_tree(tag_tree) + end_marker

    return result


def _scan_line_for_tags(line_to_scan: str) -> list[str]:
    """
    Scan a single line for tags. This is a line that looks like:
    Tags: Tag_One Tag_Two Tag_Three-Sub_Tag_A

    :param line_to_scan: line to be scanned
    :return: list of tags in that line
    """
    if line_to_scan.startswith("Tags: "):
        # return a list of tags, without the initial Tags: indicator
        return line_to_scan.split()[1:]

    else:
        return []


def _add_page_to_tag_dict(page: str, tag_seq: str, tag_dict: dict[str, any]) -> None:
    """
    Add the filename to the tag dict. The dict structure looks like:
    {
        "untagged": {"page1", "page2", "page3"}
        "tag1": {
            "untagged": ["page4"]
        }
        "tag2": {
            "untagged": {}
            "sub-tag3": {
                "untagged": {"page5", "page6"}
            }
        }
        "tag4": {
            "untagged": {"page5"}
        }
    }

    :param page: name of the page to be added to the tag_dict
    :param tag_seq: list of tags to be added
    :param tag_dict: dictionary where the tags will be added
    """
    current_dict = tag_dict
    for current_level in tag_seq.split("-"):
        current_dict = current_dict.setdefault(current_level, {"untagged": set()})
    current_dict.setdefault("untagged", set()).add(page)


def _render_tag_tree(tag_tree: dict, level: int = 2) -> str:
    """
    Render the tag tree into a string with links to the pages.

    :param tag_tree: dict containing the tags
    :param level: how many #'s to put in front of tag headings
    :return: tag tree rendered as Markdown
    """
    result = ""

    for one_filename in sorted(list(tag_tree["untagged"])):
        # strip off the extension then change dashes to spaces
        # Prefix link with 'wiki/' so that it works right
        # This is a GitHub bug
        stripped_filename = splitext(one_filename)[0]
        munged_filename = stripped_filename.translate(dash_to_space)
        result += f"[{munged_filename}](wiki/{stripped_filename})\n\n"

    sub_tags = sorted(tag_tree.keys())
    sub_tags.remove("untagged")
    for one_tag in sub_tags:
        result += f"{'#' * level} {one_tag.translate(underscore_to_space)}\n\n"
        result += _render_tag_tree(tag_tree[one_tag], level + 1)

    return result

