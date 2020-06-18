import codecs
import csv
import filecmp
import os
import time
import click
import pyimgur
import requests
from hacktools import common, wii

version = "1.3.2"
isofile = "data/disc.iso"
infolder = "data/extract/"
outfolder = "data/repack/"
replacefolder = "data/replace/"
patchin = "data/extract/DATA/files/"
patchout = "data/repack/DATA/files/"
patchfolder = "data/patch/monopri/"
xmlfile = "data/patch/riivolution/monopri.xml"


@common.cli.command()
@click.option("--iso", is_flag=True, default=False)
@click.option("--msbe", is_flag=True, default=False)
@click.option("--movie", is_flag=True, default=False)
@click.option("--tpl", is_flag=True, default=False)
@click.option("--speaker", is_flag=True, default=False)
def extract(iso, msbe, movie, tpl, speaker):
    all = not iso and not msbe and not movie and not tpl
    if all or iso:
        wii.extractIso(isofile, infolder, outfolder)
    if all or msbe:
        import extract_msbe
        extract_msbe.run(speaker)
    if all or movie:
        import extract_movie
        extract_movie.run()
    if all or tpl:
        wii.extractARC("data/extract/DATA/files/lytdemo/exp_data/", "data/extract_TPL/")
        common.copyFolder("data/extract/DATA/files/textures/", "data/extract_TPL/textures/")
        wii.extractTPL("data/extract_TPL/", "data/out_TPL/")


@common.cli.command()
@click.option("--no-patch", is_flag=True, default=False)
@click.option("--msbe", is_flag=True, default=False)
@click.option("--onlyquest", is_flag=True, default=False)
@click.option("--movie", is_flag=True, default=False)
@click.option("--tpl", is_flag=True, default=False)
def repack(no_patch, msbe, onlyquest, movie, tpl):
    all = not msbe and not movie and not tpl
    if all or msbe:
        import repack_msbe
        repack_msbe.run(onlyquest)
    if all or movie:
        import repack_movie
        repack_movie.run()
    if all or tpl:
        import repack_tpl
        repack_tpl.run()
    if os.path.isdir(replacefolder):
        common.mergeFolder(replacefolder, outfolder)

    if not no_patch:
        common.makeFolders(patchfolder)
        common.makeFolder(patchfolder.replace("monopri/", "riivolution/"))
        common.logMessage("Creating patch folder in", patchfolder, "...")
        files = common.getFiles(patchin)
        for file in common.showProgress(files):
            if not filecmp.cmp(patchin + file, patchout + file):
                common.makeFolders(patchfolder + os.path.dirname(file))
                common.copyFile(patchout + file, patchfolder + file)
        with common.Stream(xmlfile, "w") as f:
            f.writeLine('<wiidisc version="1">')
            f.writeLine('\t<id game="RSEJGD"/>')
            f.writeLine('\t<options>')
            f.writeLine('\t\t<section name="Translation">')
            f.writeLine('\t\t\t<option name="Translation Patch">')
            f.writeLine('\t\t\t\t<choice name="Enabled">')
            f.writeLine('\t\t\t\t\t<patch id="monoprifolder"/>')
            f.writeLine('\t\t\t\t</choice>')
            f.writeLine('\t\t\t</option>')
            f.writeLine('\t\t</section>')
            f.writeLine('\t</options>')
            f.writeLine('\t<patch id="monoprifolder">')
            f.writeLine('\t\t<folder external="/monopri" recursive="false"/>')
            f.writeLine('\t\t<folder external="/monopri" disc="/"/>')
            f.writeLine('\t</patch>')
            f.writeLine('</wiidisc>')
        common.logMessage("Done!")


@common.cli.command()
@click.argument("clientid")
def generatepo(clientid):
    tplfolder = "data/work_TPL"
    tploriginal = "data/out_TPL"
    files = common.getFiles(tplfolder)
    im = pyimgur.Imgur(clientid)
    with common.Stream("data/tpl.po", "w") as f:
        for file in common.showProgress(files):
            uploaded = False
            while not uploaded:
                try:
                    image = im.upload_image(tploriginal + file, title="file")
                    f.writeLine("#. " + image.link)
                    f.writeLine("msgid \"" + file.split("/")[2] + "\"")
                    f.writeLine("msgstr \"\"")
                    f.writeLine("")
                    uploaded = True
                    time.sleep(30)
                except requests.HTTPError:
                    time.sleep(300)
    common.logMessage("Done!")


def cleanSection(section):
    for str in section:
        newlist = []
        for trans in section[str]:
            if trans != "":
                newlist.append(trans)
        if len(newlist) == 0:
            section[str] = [""]
        else:
            section[str] = newlist
    return section


@common.cli.command()
def smartcat():
    click.confirm("Importing Smartcat CSV will override the msbe_input.txt file, are you sure?", abort=True)
    common.logMessage("Importing Smartcat CSV ...")
    # Read the lines from the CSV files
    infiles = ["data/msbe_output_rearranged.csv", "data/msbe_events.csv", "data/msbe_system.csv"]
    section = {}
    commons = {}
    current = ""
    for file in infiles:
        with open(file, newline="", encoding="utf-8") as csvfile:
            rows = csv.reader(csvfile, delimiter=",", quotechar="\"")
            for row in rows:
                orig = row[0]
                trans = row[1]
                if orig == "ja" or ".png" in orig or "youtube.com" in orig or orig == "Table of Contents:" or orig == "!Images":
                    continue
                if orig.startswith("("):
                    orig = orig.split(") ", 1)[1]
                if orig != "":
                    if orig.startswith("!FILE:"):
                        current = orig.split(",")[0].replace("!FILE:", "")
                        section[current] = {}
                    elif current != "":
                        if orig in section[current]:
                            section[current][orig].append(trans)
                        else:
                            section[current][orig] = [trans]
                        if orig in commons:
                            commons[orig].append(trans)
                        else:
                            commons[orig] = [trans]
    # Clean up empty lines that have translations somewhere else
    commons = cleanSection(commons)
    for name in section:
        section[name] = cleanSection(section[name])
    # Export everything to msbe_input following msbe_output for ordering
    with codecs.open("data/msbe_output.txt", "r", "utf-8") as fin:
        with codecs.open("data/msbe_input.txt", "w", "utf-8") as f:
            current = ""
            for line in fin:
                line = line.rstrip("\r\n").replace("\ufeff", "")
                if line.startswith("!FILE:"):
                    current = line.replace("!FILE:", "")
                    if current not in section:
                        common.logWarning("Section", current, "not found")
                        current = ""
                    else:
                        f.write("!FILE:" + current + "\n")
                elif current != "":
                    line = line.replace("=", "")
                    sectionline = line
                    if line not in section[current]:
                        if line.strip(" 　") in section[current] or line.strip(" 　") in commons:
                            sectionline = line.strip(" 　")
                        elif line.replace("<3D>", "=") in section[current] or line.replace("<3D>", "=") in commons:
                            sectionline = line.replace("<3D>", "=")
                    if sectionline not in section[current] and sectionline in commons:
                        section[current][sectionline] = commons[sectionline]
                    if sectionline in section[current]:
                        f.write(line + "=" + section[current][sectionline][0] + "\n")
                        if len(section[current][sectionline]) > 1:
                            section[current][sectionline].pop()
                    else:
                        f.write(line + "=\n")
                        common.logWarning("Line \"" + sectionline + "\" in section", current, "not found")
    common.logMessage("Done!")


if __name__ == "__main__":
    click.echo("MonoPriTranslation version " + version)
    if not os.path.isdir("data"):
        common.logError("data folder not found.")
        quit()
    common.cli()
