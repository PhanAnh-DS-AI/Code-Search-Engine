from typing import List, Optional

class MetaData:
    def __init__(self, stars: int, owner: str, url: str, id: int):
        self.stars = stars
        self.owner = owner
        self.url = url
        self.id = id

    def to_dict(self):
        return {
            "stars": self.stars,
            "owner": self.owner,
            "url": self.url,
            "id": self.id,
        }

class RepoDoc:
    def __init__(self, title: str, short_des: str, tags: List[str], date: str, meta_data: MetaData, score: float = 0.0):
        self.title = title
        self.short_des = short_des
        self.tags = tags
        self.date = date
        self.meta_data = meta_data
        self.score = score

    def to_dict(self):
        return {
            "title": self.title,
            "short_des": self.short_des,
            "tags": self.tags,
            "date": self.date,
            "meta_data": self.meta_data.to_dict(),
            "score": self.score,
        }