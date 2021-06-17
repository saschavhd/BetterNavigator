import asyncio
import discord
from discord.ext import commands
from typing import Union, Optional


class Page():
    def __init__(self, **kwargs):

        # Class handled
        self._list_emojis = {
        'numbers': [':zero:', ':one:', ':two:', ':three:',
                    ':four:', ':five:', ':six:', ':seven:',
                    ':eight:', ':nine:']
        }

        # User input
        self.options = kwargs

        self.content = kwargs.get('content', '')
        self.title = kwargs.get('title', '')
        self.description = kwargs.get('description', '')
        self.footer = kwargs.get('footer', '')

        if not self.content and not self.title and not self.description:
            raise RuntimeError("Page is completely empty.")

        self.prefix = kwargs.get('prefix', '')
        self.enumerate = kwargs.get('enumerate', False)
        self.enumerate_with_emoji = kwargs.get('enumerate_with_emoji', False)

        self.display = kwargs.get('display', 'line')

        if isinstance(self.content, str):
            self.enlisted = False

        elif isinstance(self.content, (list, tuple)):
            self.enlisted = True

        else:
            raise TypeError("Required attribute content must be of type string, ",
            f"list or tuple. Not {type(content)}")

    def __str__(self):
        if not self.content:
            return ""

        if self.display == 'block' and self.enumerate_with_emoji:
            print("Warning: cannot display emojis when keyword attribute `display` is set to 'block'.")

        if self.enlisted:
            return ''.join([f"{self._prefix[itr]}{entry}\n" for itr, entry in enumerate(self.content)]).rstrip()
        else:
            return self.content

    def __len__(self):
        return len(self._content)

    @property
    def _prefix(self):
        if self.enumerate_with_emoji:
            if self.display != 'block':
                return [f"{self._get_emoji_number(itr+1)} " for itr in range(len(self.content))]
        if self.enumerate or self.enumerate_with_emoji:
            return [f"{itr+1} " for itr in range(len(self.content))]
        else:
            return [f"{self.prefix}{' ' * (self.prefix != '')}"] * len(self.content)

    @property
    def _content(self):
        head = ""
        if self.title:
            head += f"**{self.title}**\n"
        if self.description:
            head += f"*{self.description}*\n"
        if self.title or self.description:
            head += "\n"
        content = head + str(self)
        if self.footer:
            content += f"\n\n*{self.footer}*"
        if self.display == 'block':
            content = f"```{content}```"

        return content

    def _get_emoji_number(self, number: int) -> str:
        '''
        Turns postive integer into discord emoji

        Parameters:
        -----------
            number: :class:`int`
                Integer to convert to emoji string

        Returns:
        --------
            emoji_number: :class:`str`
                (Combined) string version of the integer
        '''

        if number < 0:
            raise NotImplementedError("Method _get_emoji_number does not yet ",
            "convert negative integers.")

        emoji_number = ''
        for char in str(number):
            emoji_number += f"{self._list_emojis['numbers'][int(char)]}"
        return emoji_number


class EmbeddedPage(Page):
    def __init__(self, title: str, **kwargs):
        super().__init__(title=title, **kwargs)

        self.using_fields = kwargs.get('using_fields', False)
        if self.using_fields:
            if not isinstance(self.content, (list, tuple)):
                raise TypeError(
                "When optional keyword attribute `using_fields` is set to true ",
                "required attribute `content` must be of type list or tuple.",
                f"Not {type(content)}.")
            self.enlisted = True

        self.author = kwargs.get('author', None)
        self.timestamp = kwargs.get('timestamp', None)

        try:
            self.image = kwargs['image_url']
        except KeyError:
            self.image = kwargs.get('image', None)

        try:
            self.thumbnail = kwargs['thumnail_url']
        except KeyError:
            self.thumbnail = kwargs.get('thumbnail', None)

        try:
            self.colour = kwargs['color']
        except KeyError:
            self.colour = kwargs.get('colour', discord.Colour.default())

    @property
    def embed(self):
        embed = discord.Embed(
            title=f"{self.title}",
            colour=self.colour
        )

        if self.description:
            embed.description = f"*{self.description}*"

        if self.content:
            if self.using_fields:
                for itr, entry in enumerate(self.content):
                    embed.add_field(name=self._prefix[itr], value=entry)
            else:
                embed.description += f"\n\n{str(self)}"

        if self.footer:
            embed.set_footer(text=self.footer)

        return embed
