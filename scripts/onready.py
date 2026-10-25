
import time
import traceback
import asyncio

class onready:
    def __init__(self, bot=None):
        self.bot = bot
        self.task_queue = asyncio.Queue()
        self.worker_task = None

        async def B_on_ready():
            global dev_channel
            global dev_server
            global starttime
            global accepting_commands
            global welc_channel
            global fennec

            self.worker_task = None

            print(f'skynet initialized: {bot.user}')

            dev_server = bot.get_guild(1345760072776679495)

            if dev_server is None:
                print("ERROR: Dev server not found")
                return

            dev_channel = dev_server.get_channel(1347697748518113360)

            if dev_channel is None:
                for channel in dev_server.channels:
                    if channel.name == 'general3':
                        dev_channel = channel
                        break

            print(f'skynet dev server connection established: {dev_server} -> {dev_channel}')

            fennec = bot.get_guild(1559718691090731048)

            if fennec is None:
                print("ERROR: Fennec server not found")
                return

            welc_channel = fennec.get_channel(1560093667794878566)

            if welc_channel is None:
                for channel in fennec.channels:
                    if channel.name == '𝒲﹐welc﹗':
                        welc_channel = channel
                        break

            print(f'skynet welc channel established: {welc_channel}')

            starttime = time.time()
            print(f'starttime: {starttime:.2f}')
            accepting_commands = True

            if self.worker_task is None or self.worker_task.done():
                self.worker_task = asyncio.create_task(self.task_worker())

        async def task_worker():
            while True:
                task = await self.task_queue.get()

                try:
                    await task()
                except Exception:
                    print('skynet: ERROR - task failed')
                    traceback.print_exc()
                finally:
                    self.task_queue.task_done()

        self.task_worker = task_worker
        self.onreadyfunc = B_on_ready
