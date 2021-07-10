import asyncio
import discord
from discord.ext import commands
from typing import Union


class Page():
    '''
    A class to handle the formatting of message information
    This class is only used as a supplement to Menu.

    Attributes:
    -----------
        All attributes are optional, however if the right combination of optional
        arguments is not met, the page might not be able to display information properly.

        content: :class:`Union[str, list[str]]`
            Either a string or sequence of strings to represent the page content.
            If a list is passed through this will set `enlisted` to True.
        title: :class:`str`
            The title of the page, will be bold by default.
        description: :class:`description`
            The description of the page, will be cursive by default.
        footer: :class:`footer`
            The footer of the page, note that in a menu object the page number
            will always be added to this footer.

        prefix: :class:`str`
            When enlisted is set to true the `prefix` will be used as a list character.
        enumerate: :class:`bool`
            Whether to number the enlisted content, overwrites any set prefix.
        enumerate_with_emoji: :class:`bool`
            Whether to number the enlisted content with an emoji (e.g. :one:).
            This overwrite both prefix and enumerate.

        display: :class:`str`
            How to display the content, by default it is set to line, which
            looks like normal discord message. However this attribute can be set
            to block to "engrave" (```{content}```) the content.
    '''
    def __init__(self, **kwargs):

        # Content handling
        self.content = kwargs.get('content', '')
        if isinstance(self.content, str):
            self.enlisted = False
        elif isinstance(self.content, list):
            self.enlisted = True
        else:
            raise TypeError("Required attribute content must be of type string " +
            f"or list. Not {type(self.content)}")

        # Header and footer information
        self.title = kwargs.get('title', '')
        self.description = kwargs.get('description', '')
        self.footer = kwargs.get('footer', '')

        # Check if page not empty
        if not self.content and not self.title and not self.description:
            raise RuntimeError("Page is completely empty.")

        # List formatting options
        self.prefix = kwargs.get('prefix', '')
        self.enumerate = kwargs.get('enumerate', False)
        self.enumerate_with_emoji = kwargs.get('enumerate_with_emoji', False)

        # Text formatting options
        self.display = kwargs.get('display', 'line')

        # Class handled
        self._list_emojis = {
        'numbers': [':zero:', ':one:', ':two:', ':three:',
                    ':four:', ':five:', ':six:', ':seven:',
                    ':eight:', ':nine:']
        }

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
    def _prefix(self) -> list[str]:
        if self.enumerate_with_emoji:
            if self.display != 'block':
                return [f"{self._get_emoji_number(itr+1)} " for itr in range(len(self.content))]
        if self.enumerate or self.enumerate_with_emoji:
            return [f"{itr+1} " for itr in range(len(self.content))]
        elif isinstance(self.prefix, list):
            return [f"{prefix} "for prefix in self.prefix]
        else:
            return [f"{self.prefix}{' ' * (self.prefix != '')}"] * len(self.content)

    @property
    def _content(self) -> str:
        head = ""
        if self.title:
            head += f"**{self.title}**\n"
        if self.description:
            head += f"*{self.description}*\n"
        if self.title or self.description:
            head += "\n"
        content = head + str(self)
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
    '''
    A subclass of page, inheriting it's content properties.
    The additional keyword arguments for this class are just passthrough
    arguments of a discord.Embed object.
    See here for more information:
        https://discordpy.readthedocs.io/en/latest/api.html?#discord.Embed
    '''

    def __init__(self, title: str, **kwargs):
        super().__init__(title=title, **kwargs)

        self.using_fields = kwargs.get('using_fields', False)
        if self.using_fields:
            if not isinstance(self.content, list):
                raise TypeError(
                "When optional keyword attribute `using_fields` is set to true ",
                "required attribute `content` must be of type list.",
                f"Not {type(self.content)}.")
            self.enlisted = True

        self.author = kwargs.get('author', None)
        self.timestamp = kwargs.get('timestamp', None)
        self.inline = kwargs.get('inline', False)

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
    def embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.title}",
            colour=self.colour
        )

        if self.description: embed.description = f"*{self.description}*"

        if self.content:
            if self.using_fields:
                for itr, entry in enumerate(self.content):
                    embed.add_field(name=self._prefix[itr], value=entry, inline=self.inline)
            else:
                if not embed.description:
                    embed.description=" "
                embed.description += f"\n\n{str(self)}"

        if self.footer: embed.set_footer(text=self.footer)

        if self.image: embed.set_image(url=self.image)

        if self.thumbnail: embed.set_thumbnail(url=self.thumbnail)

        return embed
