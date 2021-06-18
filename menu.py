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
        title: :class:`str`
            The menu's default title that might be inherited.
        overwrite_title: :class:`bool`
            Whether to overwrite individually set page titles.
        fill_title: :class:`bool`
            Whether to fill the default title to pages that have no title

        description: :class:`str`
            The menu's default description that might be inherited.
        overwrite_description: :class:`bool`
            Whether to overwrite individually set page descriptions.
        fill_title: :class:`bool`
            Whether to fill the default description to pages that have none

        footer: :class:`str`
            The menu's default footer that might be inherited.
        overwrite_footer: :class:`bool`
            Whether to overwrite indivually set page footers.
        fill_footer: :class:`bool`
            Whether to fill the default footer to pages that have no footer.

        overwrite_all: :class:`bool`
            Whether to overwrite all default menu information, not overwritten
            individually.
        fill_all: :class:`bool`
            Whether to fill all default menu information. Overwritten indiviually.

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

        # Collection of keyword arguments
        self.options = kwargs

        # Page options
        self.title = kwargs.get('title', '')
        self.overwrite_title = kwargs.get('overwrite_title', False)
        self.fill_title = kwargs.get('fill_title', True)

        self.description = kwargs.get('description', '')
        self.overwrite_description = kwargs.get('overwrite_description', False)
        self.fill_description = kwargs.get('fill_description', True)

        self.footer = kwargs.get('footer', '')
        self.overwrite_footer = kwargs.get('overwrite_footer', False)
        self.fill_footer = kwargs.get('fill_footer', True)

        self.overwrite_all = kwargs.get('overwrite_all', False)
        self.fill_all = kwargs.get('fill_all', True)

        self.enumerate = kwargs.get('enumerate', False)
        self.enumerate_with_emoji = kwargs.get('enumerate_with_emoji', False)
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
    def _page_options(self) -> dict:
        self.options['title'] = self.title
        self.options['description'] = self.description
        self.options['footer'] = self.footer
        return self.options

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
    def _overwrite_title(self) -> bool:
        return (self.overwrite_title or self.overwrite_all)

    @property
    def _fill_title(self) -> bool:
        return (self.fill_title and self.fill_all)

    @property
    def _overwrite_description(self) -> bool:
        return (self.overwrite_description or self.overwrite_all)

    @property
    def _fill_description(self) -> bool:
        return (self.fill_description and self.fill_all)

    @property
    def _overwrite_footer(self) -> bool:
        return (self.overwrite_footer or self.overwrite_all)

    @property
    def _fill_footer(self) -> bool:
        return (self.fill_footer and self.fill_all)

    @property
    def current_embed(self) -> discord.Embed:
        if isinstance(self.current_page, EmbeddedPage):
            embed = self.current_page.embed
            if self.current_page.footer:
                embed.set_footer(text=self.current_page.footer)
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
                    content = content[:-3] + f"\n\n{self._footer}" + content[-3:]
                else:
                    content += f"\n\n{self._footer}"
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
            if self._overwrite_title:
                page.title = self.title
            elif not page.title and self.fill_title:
                page.title = self.title

            if self._overwrite_description:
                page.description = self.description
            elif not page.description and self.fill_description:
                page.description = self.description

            if self._overwrite_footer:
                page.footer = self.footer
            elif not page.footer and self.fill_footer:
                page.footer = self.footer

            if page.enlisted:
                if self.enumerate_with_emoji:
                    page.enumerate_with_emoji = True
                elif self.enumerate:
                    page.enumerate = True

        elif isinstance(page, (str, list[str])):
            if self.all_embedded:
                page = EmbeddedPage(content=page, **self._page_options)
            else:
                page = Page(content=page, **self._page_options)
        else:
            raise TypeError("Items in required attribute `pages` must all be of type Page, str, list or tuple")
        return page

    def update(self, pages: Union[list[Page, str, list]]=None):
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
        if self.show_buttons:
            if self.selectors:
                for selector in self.selectors:
                    await self.message.add_reaction(selector)

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

                if self.selectors:
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self._check_selector))
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

                    if self.reaction_input:
                        return (payload, self.current_page)

                    if str(payload.emoji) in self.selectors:
                        return (payload, self.current_page)

                    user = self.bot.get_user(payload.user_id)
                    message.remove_reaction(payload.emoji, user)

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
