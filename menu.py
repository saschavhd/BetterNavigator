import asyncio
import discord
from discord.ext import commands
from typing import Union, Optional
from page import Page, EmbeddedPage

# Minimum needed permissions:
# View whatever needed channel
# Send messages, edit messages and add reactions


class Menu():
    '''
    An extension class providing for a highly customizable dynamic menu.

    Attributes:
    -----------
        bot: class:`commands.Bot`
            Bot that will be used to create the menu.

        pages: class:`list[Union[Page, str, list[str]]]`
            Sequence of Pages, if item in list is not given as type `Page`,
            it will be converted to one inheriting the menu's options.

        interactors: class:`list`
            Sequence of discord users allowed to interact with the menu.
            (Currently asks for a list of `discord.User` objects however,
            could be easily changed to ask a list of just id's instead.)

        channel: class:`discord.TextChannel, discord.DMChannel`
            Channel the menu message will be displayed in.
            Currently supports text- and direct message channels

    Keyword Attributes:
    -------------------
        These attributes will in most situations not be necessary for
        functionality with the set default values. However these can
        be changed to liking for higher customization.

        Page Formatting Attributes:
        ------------------------
        page_options: :class:`dict`
            A dictionary containing the formatting for the pages in the menu.

        overwrite_page_options: :class:`bool`
            Whether to overwrite all page formatting with "page_options".
            This means change them regardless of whether they have the attributes.
        fill_page_options: :class:`bool`
            Whether to fill all page formatting with "page_options".
            This means adding the attribute if they don't have it yet.

        all_embedded: :class:`bool`
            Whether all pages created by the menu itself will be embeds.

        Input Attributes:
        -----------------
        If input variables are given then extra tasks will be added, when these
        tasks are completed the start method will return a `tuple` consisting
        of the payload and the Page the input was given on.

        input: :class:`Callable`
            Custom function that would check if user message input is valid.
        reaction_input: :class:`Callable`
            Custom function that would check if user reaction is valid.
        selectors: :class:`list`
            A list of emojis that will be appended to the menu, when one is
            chosen it will be returned as payload.

        Menu Formatting Attributes:
        ---------------------------
        show_page_number: :class:`bool`
            Whether to show the page number in the footer, if there is only one
            page then this will be False by default.
        show_buttons: :class:`bool`
            whether to display any buttons at all.
        show_general_buttons: :class:`bool`
            Whether to show buttons from general category

        remove_reactions_after: class:`bool`
            Whether to remove reactions upon stopping the menu.
        remove_message_after: class:`bool`
            Whether to remove message upon stopping the menu.
    '''

    def __init__(self,
                 bot: commands.Bot,
                 pages: list[Union[Page, str, list[str]]],
                 interactors: Union[list[discord.User], tuple[discord.User]],
                 channel: Union[discord.TextChannel, discord.DMChannel],
                 **kwargs):

        # Required user input
        self.bot = bot
        self.interactors = interactors
        self.channel = channel

        # Page options
        self.options = kwargs

        self.overwrite_options = kwargs.get('overwrite_all', False)
        self.fill_options = kwargs.get('fill_all', True)

        self.all_embedded = kwargs.get('all_embedded', False)

        self.update(pages=pages)

        # Input & Asyncio options
        self.input = kwargs.get('input', False)
        self.reaction_input = kwargs.get('reaction_input', False)
        self.timeout = kwargs.get('timeout', 60)
        self.selectors = kwargs.get('selectors', None)

        # Menu formatting options
        self.show_page_number = kwargs.get('show_page_number', True)
        self.show_buttons = kwargs.get('show_buttons', True)
        self.show_general_buttons = kwargs.get('show_general_buttons', True)
        self.remove_reactions_after = kwargs.get('remove_reactions_after', True)
        self.remove_message_after = kwargs.get('remove_message_after', False)

        self.current_page_number = 1
        self._running = False
        self.message = None

        self._buttons = {
            'navigation': {
                '⏪': self.first_page,
                '◀️': self.previous_page,
                '▶️': self.next_page,
                '⏩': self.last_page
            },
            'general': {
                '❌': self.stop
            }
        }

        self._all_buttons = {**self._buttons['navigation'], **self._buttons['general']}

    @property
    def current_page(self) -> Page:
        return self.pages[self.current_page_number-1]

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def _show_page_number(self) -> bool:
        if len(self.pages) == 1:
            return False
        else:
            return self.show_page_number

    @property
    def _show_nav_buttons(self) -> bool:
        if len(self.pages) == 1:
            return False
        else:
            return True

    @property
    def _footer(self) -> str:
        footer = ""
        if self.current_page.footer:
            footer = f"{self.current_page.footer}"
        if self.current_page.footer and self._show_page_number:
            footer += " | "
        if self._show_page_number:
            footer += f"page {self.current_page_number}/{self.total_pages}"
        return footer

    @property
    def current_embed(self) -> discord.Embed:
        if isinstance(self.current_page, EmbeddedPage):
            embed = self.current_page.embed
            if self._footer:
                embed.set_footer(text=self._footer)
            return embed
        else:
            return None

    @property
    def current_content(self) -> str:
        if isinstance(self.current_page, EmbeddedPage):
            return None
        else:
            content = self.current_page._content
            if self._footer:
                if self.current_page.display == 'block':
                    content = content[:-3] + f"\n\n*{self._footer}*" + content[-3:]
                else:
                    content += f"\n\n*{self._footer}*"
            return content

    def update_page(self, page: Union[Page, str, list[str]]):
        '''
        Updates or creates a page and alignes it's properties
        according to all menu options.

        Parameters:
        -----------
            page: class:`Union[Page, str, list[str]]`
                Page to update, create or align.

        Returns:
        --------
            page: class:`Page`
                Created or updated Page object.
        '''

        if isinstance(page, Page):
            for attribute, value in self.options.items():
                if self.overwrite_options:
                    try:
                        setattr(page, attribute, value)
                    except AttributeError:
                        pass
                elif self.fill_options:
                    try:
                        if not getattr(page, attribute, value):
                            setattr(page, attribute, value)
                    except AttributeError:
                        pass

        elif isinstance(page, (str, list)):
            if self.all_embedded:
                page = EmbeddedPage(content=page, **self.options)
            else:
                page = Page(content=page, **self.options)
        else:
            raise TypeError("Items in required attribute `pages` must all be of type Page, str or list.")
        return page

    def update(self, pages: Union[list[Page, str, list[str]]]=None):
        '''
        Updates all pages in the menu, if keyword argument `pages` is
        given then the menu's current pages will be overwritten by it.

        Parameters:
        -----------
            pages: :class:`Union[list[Page, str, list]]`
                New pages sequence to used to overwrite current pages
        '''

        if pages:
            self.pages = pages

        for itr, page in enumerate(self.pages):
            self.pages[itr] = self.update_page(page)

    def _check_selector(self, payload: discord.RawReactionActionEvent) -> bool:
        '''
        Checks whether payload should be processed as a input selector

        Parameters:
        -----------
            payload: :class:`discord.RawReactionActionEvent`
                payload to check

        Returns:
        --------
            check: :class:`bool`
                whether reaction is a correct selection
        '''

        return (
            not self.bot.get_user(payload.user_id).bot and
            payload.message_id == self.message.id and
            payload.user_id in [intor.id for intor in self.interactors] and
            str(payload.emoji) in self.selectors
        )

    def _check_button(self, payload: discord.RawReactionActionEvent) -> bool:
        '''
        Checks whether payload should be processed as a functional button

        Parameters:
        -----------
            payload: discord.RawReactionActionEvent
                payload to check

        Returns:
        --------
            check: class:`bool`
                whether to process button function
        '''

        return (
            not self.bot.get_user(payload.user_id).bot and
            payload.message_id == self.message.id and
            payload.user_id in [intor.id for intor in self.interactors] and
            str(payload.emoji) in self._all_buttons
        )

    async def display(self, new: bool=True, reset_position: bool=True) -> tuple:
        '''
        Creates message and starts interactive navigation

        Parameters:
        -----------
            new: :class:`bool`
                Whether to make a new message or continue on the old one.
                If no old message exists a new one will be created regardless.

            reset_positon: :class:`bool`
                Whether to start from page 1 or from the last saved page number.

        Returns:
        --------
            :class:`tuple`:
                self.current_page: :class:`Page`
                    Page at the time of receiving correct input

                Union:
                    message: :class:`discord.Message`
                        User input message
                    reaction :class:`discord.RawReactionActionEvent`
                        User reaction input payload
        '''

        # Check if message
        if not self.message and not new:
            raise RuntimeError("Cannot continue if message was deleted or never created. ",
                               " (Set `new` to True or leave it default)")

        if reset_position:
            self.current_page_number = 1

        if not new:
            try:
                await self.message.clear_reactions()
            except discord.Forbidden:
                await self.message.delete()
                new = True

        content, embed = self.current_content, self.current_embed
        if new:
            self.message = await self.channel.send(content=content, embed=embed)
        else:
            await self.message.edit(content=content, embed=embed)

        # Add buttons to message
        if self.selectors:
            for selector in self.selectors:
                await self.message.add_reaction(selector)

        if self.show_buttons:

            if self._show_nav_buttons:
                for button in self._buttons['navigation']:
                    await self.message.add_reaction(button)

            if self.show_general_buttons:
                for button in self._buttons['general']:
                    await self.message.add_reaction(button)

        # Start main interaction loop
        try:
            self._running = True
            tasks = []

            while self._running:

                tasks = [
                    asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self._check_button)),
                    asyncio.create_task(self.bot.wait_for('raw_reaction_remove', check=self._check_button))
                ]

                if self.input:
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('message', check=self.input))
                    )

                if self.reaction_input:
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self.reaction_input))
                    )
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('raw_reaction_remove', check=self.reaction_input))
                    )

                if self.selectors:
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self._check_selector))
                    )
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('raw_reaction_remove', check=self._check_selector))
                    )

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
                    emoji = payload.emoji
                except AttributeError:
                    pass
                else:
                    try:
                        await self._all_buttons[str(emoji)]()
                    except KeyError:
                        pass
                    else:
                        continue

                    if self.reaction_input:
                        return (payload, self.current_page)

                    if str(emoji) in self.selectors:
                        return (payload, self.current_page)

                    user = self.bot.get_user(payload.user_id)
                    message.remove_reaction(emoji, user)

                try:
                    message_content = payload.content
                except AttributeError:
                    pass
                else:
                    return (payload, self.current_page)

        except asyncio.TimeoutError:
            await self.stop()

        finally:
            for task in tasks:
                task.cancel()

    async def stop(self):
        self._running = False
        if self.remove_message_after:
            try:
                await self.message.delete()
            except discord.NotFound:
                return

        if self.remove_reactions_after:
            try:
                await self.message.clear_reactions()
            except discord.NotFound:
                return
            except discord.Forbidden:
                pass

    def update_message(func):
        '''Decorator to update the message'''
        async def update_message_wrapper(self):
            await func(self)
            try:
                await self.message.edit(content=self.current_content, embed=self.current_embed)
            except discord.NotFound:
                raise discord.NotFound("Message was deleted or never created!")
        return update_message_wrapper

    @update_message
    async def add_page(self, page: Union[Page, str, list[str]], position: int=None):
        '''
        Add a Page to a live menu at a certain position.

        Parameters:
        -----------
            page: :class:`Union[Page, str, list, list[str]]`
                The page to add to the menu

            position: :class:`int`
                Position in the menu to place page in. This will push back
                all pages behind the position by 1.
        '''
        if not position: position = self.total_pages

        self.pages.insert(position-1, self.update_page(page))

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
