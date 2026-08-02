# core/models.py
class Machine:
    def __init__(self, id=None, name='', description='', cloneof='', romof='', manufacturer='',
                 year='', sourcefile='', runnable=0, isbios=0, isdevice=0, ismechanical=0,
                 working=0, players=0, category='', genre='', genre_ows='', machine_category='',
                 machine_type='', resolution='', version='', working_arcade=0):
        self.id = id
        self.name = name
        self.description = description
        self.cloneof = cloneof
        self.romof = romof
        self.manufacturer = manufacturer
        self.year = year
        self.sourcefile = sourcefile
        self.runnable = runnable
        self.isbios = isbios
        self.isdevice = isdevice
        self.ismechanical = ismechanical
        self.working = working
        self.players = players
        self.category = category
        self.genre = genre
        self.genre_ows = genre_ows
        self.machine_category = machine_category
        self.machine_type = machine_type
        self.resolution = resolution
        self.version = version
        self.working_arcade = working_arcade

    def __repr__(self):
        return f"<Machine {self.name}>"