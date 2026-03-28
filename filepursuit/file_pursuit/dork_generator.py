"""
Dork Generator for FilePursuit.

Generates search queries (dorks) for different file types and categories.
"""

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum


class DorkCategory(Enum):
    """Supported file categories for dorking."""
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    BOOK = "book"
    EBOOK = "ebook"
    ISO = "iso"
    DOCUMENT = "document"
    SOURCE = "source"
    ARCHIVE = "archive"


@dataclass
class DorkQuery:
    """Represents a single dork query."""
    query: str
    category: str
    site: str  # 'google', 'archive.org', 'github', 'pastebin'
    description: str = ""


class DorkGenerator:
    """Generate search queries (dorks) by category and keyword."""

    # Dork templates by category
    DORK_TEMPLATES = {
        DorkCategory.VIDEO: {
            "google": [
                'filetype:mp4 OR filetype:mkv OR filetype:avi "{keyword}"',
                'filetype:mov OR filetype:flv "{keyword}"',
                'filetype:wmv OR filetype:webm "{keyword}"',
            ],
            "archive.org": [
                'filetype:mp4 "{keyword}"',
            ],
            "github": [
                'filename:mp4 OR filename:mkv "{keyword}"',
            ],
            "pastebin": []
        },
        DorkCategory.AUDIO: {
            "google": [
                'filetype:mp3 OR filetype:flac "{keyword}"',
                'filetype:wav OR filetype:aac "{keyword}"',
                'filetype:m4a OR filetype:ogg "{keyword}"',
            ],
            "archive.org": [
                'filetype:mp3 "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        },
        DorkCategory.IMAGE: {
            "google": [
                'filetype:jpg OR filetype:jpeg OR filetype:png "{keyword}"',
                'filetype:gif OR filetype:bmp OR filetype:svg "{keyword}"',
                'filetype:webp OR filetype:tiff "{keyword}"',
            ],
            "archive.org": [
                'filetype:jpg OR filetype:png "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        },
        DorkCategory.BOOK: {
            "google": [
                'filetype:pdf "{keyword}" -site:youtube.com',
                'filetype:pdf "author" "{keyword}" OR "title"',
            ],
            "archive.org": [
                'filetype:pdf "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        },
        DorkCategory.EBOOK: {
            "google": [
                'filetype:epub OR filetype:mobi OR filetype:azw "{keyword}"',
                'filetype:prc OR filetype:ibooks "{keyword}"',
            ],
            "archive.org": [
                'filetype:epub "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        },
        DorkCategory.ISO: {
            "google": [
                'filetype:iso "{keyword}" (operating system OR software)',
                'filetype:iso "{keyword}" -torrent',
            ],
            "archive.org": [
                'filetype:iso "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        },
        DorkCategory.DOCUMENT: {
            "google": [
                'filetype:docx OR filetype:pdf OR filetype:xlsx "{keyword}"',
                'filetype:pptx OR filetype:doc OR filetype:xls "{keyword}"',
                'filetype:odt OR filetype:ods "{keyword}"',
            ],
            "archive.org": [
                'filetype:pdf OR filetype:docx "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        },
        DorkCategory.SOURCE: {
            "google": [
                'filetype:py OR filetype:js OR filetype:cpp "{keyword}"',
                'filetype:java OR filetype:go OR filetype:rs "{keyword}"',
                'filetype:c OR filetype:h OR filetype:html "{keyword}"',
            ],
            "archive.org": [],
            "github": [
                'filename:*.py "{keyword}" OR filename:*.js "{keyword}"',
                'filename:*.cpp OR filename:*.java "{keyword}"',
            ],
            "pastebin": [
                'title:"{keyword}" language:python OR language:javascript',
                'title:"{keyword}" language:cpp OR language:java',
            ]
        },
        DorkCategory.ARCHIVE: {
            "google": [
                'filetype:zip OR filetype:rar OR filetype:7z "{keyword}"',
                'filetype:tar OR filetype:gz OR filetype:bz2 "{keyword}"',
                'filetype:xz OR filetype:zip "{keyword}"',
            ],
            "archive.org": [
                'filetype:zip OR filetype:rar "{keyword}"',
            ],
            "github": [],
            "pastebin": []
        }
    }

    def __init__(self):
        """Initialize dork generator."""
        pass

    def generate_dorks(self, keyword: str, category: str) -> List[DorkQuery]:
        """
        Generate dorks for a keyword and category.

        Args:
            keyword: Search keyword
            category: File category (video, audio, image, book, ebook, iso, document, source, archive)

        Returns:
            List of DorkQuery objects
        """
        dorks = []

        # Validate category
        try:
            cat_enum = DorkCategory[category.upper()]
        except KeyError:
            return []  # Invalid category

        # Get templates for this category
        templates = self.DORK_TEMPLATES.get(cat_enum, {})

        # Generate dorks for each site
        for site, queries in templates.items():
            for query_template in queries:
                # Format with keyword
                dork_query = query_template.format(keyword=keyword)

                dorks.append(DorkQuery(
                    query=dork_query,
                    category=category,
                    site=site,
                    description=f"{site}: {dork_query[:60]}..."
                ))

        return dorks

    def generate_for_all_sites(self, keyword: str, category: str) -> Dict[str, List[DorkQuery]]:
        """
        Generate dorks grouped by site.

        Args:
            keyword: Search keyword
            category: File category

        Returns:
            Dict mapping site to list of dorks
        """
        all_dorks = self.generate_dorks(keyword, category)

        # Group by site
        by_site = {}
        for dork in all_dorks:
            if dork.site not in by_site:
                by_site[dork.site] = []
            by_site[dork.site].append(dork)

        return by_site

    def get_categories(self) -> List[str]:
        """Get list of available categories."""
        return [cat.value for cat in DorkCategory]

    def get_category_description(self, category: str) -> str:
        """Get description for a category."""
        descriptions = {
            "video": "Video files (mp4, mkv, avi, mov, flv, wmv, webm)",
            "audio": "Audio files (mp3, flac, wav, aac, m4a, ogg)",
            "image": "Image files (jpg, png, gif, bmp, svg, webp, tiff)",
            "book": "Books in PDF format",
            "ebook": "E-book formats (epub, mobi, azw, prc, ibooks)",
            "iso": "ISO images (operating systems, software)",
            "document": "Office documents (docx, pdf, xlsx, pptx, odt, ods)",
            "source": "Source code (py, js, cpp, java, go, rs, c, h, html)",
            "archive": "Compressed archives (zip, rar, 7z, tar, gz, bz2, xz)",
        }
        return descriptions.get(category, "Unknown category")

    @staticmethod
    def sample_dorks(category: str, keyword: str = "example") -> str:
        """Get sample dorks as formatted text (for manual use)."""
        generator = DorkGenerator()
        dorks = generator.generate_dorks(keyword, category)

        if not dorks:
            return f"No dorks found for category: {category}"

        output = f"Sample dorks for '{keyword}' in category '{category}':\n\n"
        output += "=" * 80 + "\n"

        by_site = {}
        for dork in dorks:
            if dork.site not in by_site:
                by_site[dork.site] = []
            by_site[dork.site].append(dork)

        for site, site_dorks in by_site.items():
            output += f"\n[{site.upper()}]\n"
            output += "-" * 40 + "\n"
            for i, dork in enumerate(site_dorks, 1):
                output += f"{i}. {dork.query}\n"

        output += "\n" + "=" * 80 + "\n"
        return output
