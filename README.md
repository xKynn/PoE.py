# PoE.py
Path of Exile wiki wrapper in python
What it can currently do:
1. Search for all possible items, including hideout doodads.  
2. Use complex filters with math operators, for example search for an item with requirement of level 42 and strength requirement of 10.  
3. Data is presented in Item/Armour/Weapon/Gem objects, all of which inherit from ItemBase
4. In utils is provided an item parser for most formats generally used in Path of Building to represent items, it can also parse a full Path of Building XML and return a dict with a lot of useful data as well as all items transformed to the objects from this lib, which allows rendering of items as images from PoB as well, rendering is covered below.  
5. Also inside utils is a parser that can parse json from path of exile's official character and skill tree API:
    - https://www.pathofexile.com/character-window/get-passive-skills?accountName=xKynn&character=Elyruse
    - https://www.pathofexile.com/character-window/get-items?accountName=xKynn&character=Elyruse
    - The dict that is returned is in the same format as the one returned by Path of Building parser, this means this also returns renderable objects
6. It can render items as on the wiki or inside the game itself in the form of PNGs using Pillow/PIL.  
    -Examples:  
      <img src="https://cdn.discordapp.com/attachments/422593979712929812/474221507380379668/test.png" width="60%"/> 
      <img src="https://cdn.discordapp.com/attachments/338371394767290369/474231185883660299/test.png" width="50%" />
      <img src="https://cdn.discordapp.com/attachments/338371394767290369/474227518958862344/test.png" width="50%" />
      <img src="https://cdn.discordapp.com/attachments/338371394767290369/473882522032406539/test.png" width="50%" />
      <img src="https://cdn.discordapp.com/attachments/338371394767290369/473757832064401408/test.png" width="50%" />
