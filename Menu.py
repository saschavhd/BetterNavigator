import asyncio
import discord
from discord.ext import commands
from typing import Union


class Menu():
    def __init__(self, bot: commands.Bot, pages: list, interactor_id: int, channel: Union[discord.TextChannel, discord.DMChannel], **kwargs):

        self._buttons = {
        '⏪': self.first_page,
        '◀️': self.previous_page,
        '▶️': self.next_page,
        '⏩': self.last_page,
        '❌': self.stop
        }

        self.bot = bot
        self.interactor_id = interactor_id
        self.channel = channel
        self.title = kwargs.get('title', None)
        self.description = kwargs.get('description', None)

        self.pages = pages
        for itr, page in enumerate(self.pages):
            if isinstance(page, Page):
                if self.title:
                    self.pages[itr].title = self.title
            elif isinstance(page, (str, list, tuple)):
                if kwargs.get('all_embedded', False):
                    self.pages[itr] = EmbeddedPage(page, self.description, self.title, **kwargs)
                else:
                    self.pages[itr] = Page(page, **kwargs)
            else:
                raise TypeError("Items in required attribute `pages` must all be of type Page, str, list or tuple")

        self.input = kwargs.get('input', False)
        self.show_page_number = kwargs.get('show_page_number', True)
        self.timeout = kwargs.get('timeout', 60)
        self.show_buttons = kwargs.get('show_buttons', True)
        self.remove_reactions_after = kwargs.get('remove_reactions_after', True)
        self.remove_message_after = kwargs.get('remove_message_after', False)

        self.current_page_number = 1
        self._running = False

        self._check_message_lengths()

    @property
    def current_page(self):
        return self.pages[self.current_page_number-1]

    @property
    def total_pages(self):
        return len(self.pages)

    def _check(self, payload: discord.RawReactionActionEvent) -> bool:
        '''
        Checks whether payload should be processed

        Parameters:
        -----------
            payload: discord.RawReactionActionEvent
                payload to check

        Returns:
        --------
            check: class:`bool`
                whether to check the payload
        '''

        return(
            payload.message_id == self._message.id and
            payload.user_id == self.interactor_id and
            str(payload.emoji) in self._buttons
        )

    async def start(self, channel: Union[discord.TextChannel, discord.DMChannel]) -> discord.Message:
        '''
        Creates message and starts interactive navigation

        Returns:
        --------
            message: :class:`Optional[discord.Message]`
        '''

        page = self.current_page
        if isinstance(page, EmbeddedPage):
            embed = page.embed
            if self.show_page_number:
                embed.set_footer(f"Page {self.current_page_number}/{self.total_pages}")
            self._message = channel.send(embed=embed)
        else:
            content = page.content
            if self.show_page_number:
                content += f"\n\nPage {self.current_page_number}/{self.total_pages}"
            self._message = await channel.send(content=content)

        if self.show_buttons:
            for button in self._buttons:
                await self._message.add_reaction(button)

        try:
            self._running = True
            tasks = []

            while self._running:

                if self.show_buttons:
                    tasks = [
                        asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self._check)),
                        asyncio.create_task(self.bot.wait_for('raw_reaction_remove', check=self._check))
                    ]

                elif self.input:
                    tasks.append(
                    asyncio.create_task(self.bot.wait_for('message', check=self.input))
                    )

                else:
                    raise ValueError("Both attributes `show_buttons` and `input` ",
                    "are False therefore no tasks were added. This is just a normal message.")

                done, pending = await asyncio.wait(
                    tasks,
                    timeout=self.timeout,
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

                if len(done) == 0:
                    raise asyncio.TimeoutError

                payload = done.pop().result()

                try:
                    await self._buttons[str(payload.emoji)]()
                except KeyError:
                    pass
                except AttributeError:
                    pass
                else:
                    continue

                try:
                    message_content = payload.content
                except AttributeError:
                    pass
                else:
                    return payload

        except asyncio.TimeoutError:
            await self.stop()

        finally:
            for task in tasks:
                task.cancel()

    async def stop(self):
        '''
        Stops interactive navigation

        Check whether to remove the message or its reactions
        '''

        self._running = False

        if self.remove_message_after:
            return await self._message.delete()

        if self.remove_reactions_after is True:
            return await self._message.clear_reactions()

    def _check_message_lengths(self):
        for i in range(1, self.total_pages):
            if isinstance(self.current_page, EmbeddedPage):
                self.current_page = page.embed
                if (len(embed) > 6000 or len(embed.description) > 2048):
                    raise ValueError("Embed size and it's description may not exceed 6000 and 2048 characters respectively.")
            elif len(self.current_page) > 2000:
                    raise ValueError("Message size may not exceed 2000 characters.")
            self.current_page_number += 1
        self.current_page_number = 1

    def update_message(func):
        '''Decorator to update the embed, mostly used for buttons'''
        async def wrapper(self, *args):
            await func(self, *args)
            if self._running:
                if isinstance(self.current_page, EmbeddedPage):
                    embed = self.current_page.embed
                    if self.show_page_number:
                        embed.set_footer(text=f"Page {self.current_page_number}/{self.total_pages}")
                    await self._message.edit(embed=embed, content="")
                else:
                    content = self.current_page.content
                    if self.show_page_number:
                        content += f"\n\nPage {self.current_page_number}/{self.total_pages}"
                    await self._message.edit(content=content, embed=None)
        return wrapper

    @update_message
    async def first_page(self):
        '''Set current page to 1'''
        self.current_page_number = 1

    @update_message
    async def last_page(self):
        '''Set current page to last (total_pages)'''
        self.current_page_number = self.total_pages

    @update_message
    async def previous_page(self):
        '''Decrement current page by 1'''
        self.current_page_number -= 1
        if self.current_page_number < 1:
            self.current_page_number = self.total_pages

    @update_message
    async def next_page(self):
        '''Increment current page by 1'''
        self.current_page_number += 1
        if self.current_page_number > self.total_pages:
            self.current_page_number = self.current_page_number - self.total_pages

    @update_message
    async def set_page(self, page_number: int):
        '''Set current page to `amount`'''
        if not(0 < page_number <= self.total_pages):
            raise ValueError(f"page_number must be between 1 and total_pages ({self.total_pages})")
        else:
            self.current_page_number = page_number


class Page():
    def __init__(self,
                content: Union[str, Union[list, tuple]],
                **kwargs):

        # Constants
        self._list_emojis = {
        'numbers': [':zero:', ':one:', ':two:', ':three:',
                    ':four:', ':five:', ':six:', ':seven:',
                    ':eight:', ':nine:']
        }

        self._raw_content = content

        self.engrave = kwargs.get('engrave_content', None)
        self.title = kwargs.get('title', None)
        self.description = kwargs.get('description', None)
        self.show_page_number = kwargs.get('show_page_number', True)

        if isinstance(content, str):
            self.enlisted = False

        elif isinstance(content, (list, tuple)):
            self.enlisted = True
            self.enumerate = kwargs.get('enumerate', False)
            self.enumerate_with_emoji = kwargs.get('enumerate_with_emoji', False)
            if self.enumerate_with_emoji:
                self.prefix = [self._get_emoji_number(itr+1) + ' ' for itr in range(len(content))]
            elif self.enumerate:
                self.prefix = [f"{itr+1} " for itr in range(len(content))]
            else:
                prefix = kwargs.get('prefix', '')
                self.prefix = [prefix + (' ' * (prefix != ''))] * len(content)
        else:
            raise TypeError("Required attribute content must be of type string, ",
            f"list or tuple. Not {type(content)}")

    def __str__(self):
        if self.enlisted:
            return ''.join([f"{self.prefix[itr]}{entry}\n" for itr, entry in enumerate(self._raw_content)]).rstrip()
        else:
            return self._raw_content

    def __len__(self):
        return len(self.content)

    @property
    def content(self):
        head = ""
        if self.title:
            head += f"{self.title}\n"
        if self.description:
            head += f"*{self.description}*\n"
        if self.title or self.description:
            head += "\n"
        return head + str(self)

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
        for char in number:
            emoji_number += f"{self._list_emojis['numbers'][int(char)]}"
        return emoji_number


class EmbeddedPage(Page):
    def __init__(self,
                content: Union[str, Union[list, tuple]],
                title: str,
                description: str,
                **kwargs):
        super().__init__(content, title=title, description=description, **kwargs)

        self.using_fields = kwargs.get('using_fields', False)
        if self.using_fields:
            if not isinstance(content, (list, tuple)):
                raise TypeError(
                "When optional keyword attribute `using_fields` is set to true ",
                "required attribute `content` must be of type list or tuple.",
                f"Not {type(content)}")
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
        description=f"*{self.description}*",
        colour=self.colour
        )

        if self.timestamp:
            embed.timestamp = self.timestamp

        if self.author:
            emed.set_author(name=self.author)

        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)

        if self.image:
            embed.set_image(url=self.image)

        if self.using_fields:
            for entry in self._raw_content:
                embed.add_field(name=self.prefix[entry], value=self._raw_content[entry])
        else:
            embed.description += f"\n\n{str(self)}"

        return embed
