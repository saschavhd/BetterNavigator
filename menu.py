import asyncio
import discord
from discord.ext import commands
from typing import Union, Optional
from page import Page, EmbeddedPage

# Minimum needed permissions:
# View whatever needed channel
# Send messages, edit messages and add reactions


class Menu():
    def __init__(self,
                 bot: commands.Bot,
                 pages: list,
                 interactors: Union[list[discord.User], tuple[discord.User]],
                 channel: Union[discord.TextChannel, discord.DMChannel],
                 **kwargs):

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

        self.bot = bot

        self.interactors = interactors
        self.channel = channel

        self.options = kwargs

        # Page settings
        self.title = kwargs.get('title', '')
        self.overwrite_title = kwargs.get('overwrite_title', False)
        self.fill_title = kwargs.get('fill_title', '')

        self.description = kwargs.get('description', '')
        self.overwrite_description = kwargs.get('overwrite_description', False)
        self.fill_description = kwargs.get('fill_description', False)

        self.footer = kwargs.get('footer', '')
        self.overwrite_footer = kwargs.get('overwrite_footer', False)
        self.fill_footer = kwargs.get('fill_footer', False)

        self.all_embedded = kwargs.get('all_embedded', False)

        self.update(pages=pages)

        self.input = kwargs.get('input', False)
        self.reaction_input = kwargs.get('reaction_input', False)

        self.timeout = kwargs.get('timeout', 60)
        self.show_page_number = kwargs.get('show_page_number', True)
        self.show_buttons = kwargs.get('show_buttons', True)
        self.show_general_buttons = kwargs.get('show_general_buttons', True)
        self.remove_reactions_after = kwargs.get('remove_reactions_after', True)
        self.remove_message_after = kwargs.get('remove_message_after', False)

        self.current_page_number = 1
        self._running = False
        self.message = None

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
    def current_embed(self) -> discord.Embed:
        try:
            embed = self.current_page.embed
        except AttributeError:
            return None
        else:
            if self.current_page_footer:
                embed.set_footer(text=self.current_page_footer)
            return embed

    @property
    def current_content(self) -> str:
        try:
            content = self.current_page._content
        except AttributeError:
            return None
        else:
            if self._footer:
                if self.current_page.display == 'block':
                    content = content[:-3] + f"\n\n{self._footer}" + content[-3:]
                else:
                    content += f"\n\n{self._footer}"
            return content

    def update_page(self, page: Union[Page, str, list, tuple]):
        if isinstance(page, Page):
            if self.overwrite_title:
                page.title = self.title
            elif not page.title and self.fill_title:
                page.title = self.title

            if self.overwrite_description:
                page.description = self.description
            elif not page.description and self.fill_description:
                page.description = self.description

            if self.overwrite_footer:
                page.footer = self.footer
            elif not page.footer and self.fill_footer:
                page.footer = self.footer

            if self.options['enumerate_with_emoji'] and page.enlisted:
                page.enumerate_with_emoji = True

        elif isinstance(page, (str, list, tuple)):
            if self.all_embedded:
                page = EmbeddedPage(content=page, **self._page_options)
            else:
                page = Page(content=page, **self._page_options)
        else:
            raise TypeError("Items in required attribute `pages` must all be of type Page, str, list or tuple")
        return page

    def update(self, pages: Union[list, tuple]=None):
        if pages:
            self.pages = pages

        for itr, page in enumerate(self.pages):
            self.pages[itr] = self.update_page(page)

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

        if not new and (not self.show_buttons or
                        not self.show_general_buttons or
                        not self._show_nav_buttons):
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
                    asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self._check)),
                    asyncio.create_task(self.bot.wait_for('raw_reaction_remove', check=self._check))
                ]

                if self.input:
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('message', check=self.input))
                    )

                if self.reaction_input:
                    tasks.append(
                        asyncio.create_task(self.bot.wait_for('raw_reaction_add', check=self.reaction_input)
                    ))

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
        if self.remove_mesage_after:
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
    async def add_page(self, page: Union[Page, str, list, tuple], position: int=0):
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
