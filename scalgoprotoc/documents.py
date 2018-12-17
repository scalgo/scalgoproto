import typing as ty
import os

Document = ty.NamedTuple(
    "Document", [("id", int), ("name", str), ("path", str), ("content", str)]
)


class Documents:
    by_name: ty.Dict[str, Document] = None
    by_id: ty.List[Document] = []
    root: Document
    lookup = []

    def __init__(self):
        self.by_name = {}
        self.by_id = []
        self.lookup = []

    def read_root(self, path: str):
        data = open(path, "r").read()
        self.lookup.append(os.path.dirname(path))
        name = os.path.splitext(os.path.basename(path))[0]
        self.root = Document(0, name, path, data)
        self.by_name[name] = self.root
        self.by_id.append(self.root)

    def read(self, name: str):
        for p in self.lookup:
            path = os.path.join(p, "%s.spr" % name)
            if os.path.isfile(path):
                data = open(path, "r").read()
                doc = Document(len(self.by_id), name, path, data)
                self.by_name[name] = doc
                self.by_id.append(doc)
                return doc
        return None


def addDocumentsParams(cmd):
    pass
