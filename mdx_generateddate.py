import markdown
import re
import datetime

# Replace the string "[GENERATED-DATE]".
datere = re.compile(r'\[GENERATED-DATE\]')
# ISO-date; Ex: "2012-09-02"
today = datetime.date.today().strftime('%Y-%m-%d')

class GeneratedDateExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        # Insert instance of date postprocessor before restoring raw HTML.
        md.postprocessors.add("generateddate", GeneratedDatePostprocessor(), "<raw_html")

class GeneratedDatePostprocessor(markdown.postprocessors.Postprocessor):
    def run(self, text):
        return datere.sub(today, text)

def makeExtension(configs=None):
    # TODO: Nothing to configure. What are possible configuration targets?
    return GeneratedDateExtension()

