import sys
import math
import random
from queue import PriorityQueue

#helpful things to keep track of
DIRECTIONS_EVEN = [[1,0],[0,-1],[-1,-1],[-1,0],[-1,1],[0,1]]
DIRECTIONS_ODD = [[1,0],[1,-1],[0,-1],[-1,0],[0,1],[1,1]]
MAP_WIDTH = 23
MAP_HEIGHT = 21
MAX_RUM_AMOUNT = 100

#keep track of the entities that are active on the map
ENTITIES = {}

#the current action our ships are doing
action = {}
prev_action = {}
prev_ship = []

mines_seen = []

LAST_CANNONBALL     = {}
LAST_MINE           = {}

CANNONBALL_COOLDOWN = 1
MINE_COOLDOWN = 4

#helper method to view debug messages
def debug(msg):
    if type(msg) is dict:
        s = str(msg)
        try:
            if msg["type"] == "BARREL":
                s = "BARREL {}, x:{}, y:{}, r:{}".format(msg["id"], msg["x"], msg["y"], msg["rum"])
            elif msg["type"] == "SHIP":
                s = "SHIP {}, x:{}, y:{}, o:{}, s:{}, r:{}, c:{}".format(msg["id"], msg["x"], msg["y"], msg["orient"], msg["speed"], msg["rum"], msg["me"])
            elif msg["type"] == "CANNONBALL":
                s = "CANNONBALL {}, x:{}, y:{}, o:{}, t:{}".format(msg["id"], msg["x"], msg["y"], msg["owner"], msg["time"])
            elif msg["type"] == "MINE":
                s = "MINE {}, x:{}, y:{}".format(msg["id"], msg["x"], msg["y"])
        except:
            pass
        
        print(s, file=sys.stderr)
    else:
        print(msg, file=sys.stderr)

#method to return all of the neighbors that are in the map of (x, y)
def neighbors(x, y):
    for d in range(6):
        cell = neighbor(x, y, d)
        if is_inside_map(cell[0], cell[1]):
            yield cell

#helper method to get the next cell in direction d from (x, y)
def neighbor(x, y, d, n=1):
    if n < 0:
        return neighbor(x, y, (d-3)%6, n=-n)
    if n == 0:
        return(x, y)
    if n == 1:
        if y%2 == 1:
            return (x + DIRECTIONS_ODD[d][0], y + DIRECTIONS_ODD[d][1])
        else:
            return (x + DIRECTIONS_EVEN[d][0], y + DIRECTIONS_EVEN[d][1])
    if n > 1:
        nx, ny = neighbor(x, y, d, n=1)
        return neighbor(nx, ny, d, n=n-1)

#returns a entity at (x, y) if one is there
def entity_at_point(x, y):
    for ent in ENTITIES.values():
        if ent in ships():
            if (x, y) in coords_of_ship(ent["id"]):
                return ent
        else:
            ent_coord = (ent["x"], ent["y"])
            if (x, y) == ent_coord:
                return ent
    return None

#determines whether or not (x, y) is inside the map
def is_inside_map(x, y):
    return x >= 0 and x < MAP_WIDTH and y >= 0 and y < MAP_HEIGHT

#returns true if there is a mine within d spaces of (x, y)
def mine_nearby(x, y, d=1):
    for mine in mines():
        if dist(x, y, mine["x"], mine["y"]) <= d:
            return True
    return False
    
#measures the distance between two points on a hex grid
def dist(x1, y1, x2, y2):
    xp1 = x1 - (y1 - (y1 & 1)) / 2
    zp1 = y1
    yp1 = -(xp1 + zp1)
    xp2 = x2 - (y2 - (y2 & 1)) / 2
    zp2 = y2
    yp2 = -(xp2 + zp2)
    return (abs(xp1 - xp2) + abs(yp1 - yp2) + abs(zp1 - zp2)) / 2

#hopefully returns the angle between two points [0-5]
def angle(sx, sy, tx, ty):
    dy = (ty - sy) * math.sqrt(3) / 2
    dx = tx - sx + ((sy - ty) & 1) * 0.5
    angle = -math.atan2(dy, dx) * 3 / math.pi
    if angle < 0:
        angle += 6
    elif angle >= 6:
        angle -= 6
    return angle

#helper to calculate cannonball time between ships
def cannonball_time_ship(ms, es):
    mx, my = coords_of_ship(ms)[0]
    ex, ey = coords_of_ship(es)[1]
    return cannonball_time(mx, my, ex, ey)

#measures the distance between the bow of ms to the center of es
def shooting_distance_ship(ms, es):
    mx, my = coords_of_ship(ms)[0]
    ex, ey = coords_of_ship(es)[1]
    return dist(mx, my, ex, ey)
    
#measures the distance between the bow of ms to the center of es
def shooting_distance(ms, x, y):
    mx, my = coords_of_ship(ms)[0]
    return dist(mx, my, x, y)
    
#number of turns for a cannonball to go from (x1, y1) to (x2, y2)
def cannonball_time(x1, y1, x2, y2):
    d = dist(x1, y1, x2, y2)
    return 1 + round(d / 3.0)
    
#predicts the enemy's location when a cannonball lands
def cannonball_predict(sx, sy, id):
    enemy = ENTITIES[id]
    tx = enemy["x"]
    ty = enemy["y"]
    to = enemy["orient"]
    ts = enemy["speed"]
    
    for x in range(1, 5):
        tx, ty = neighbor(tx, ty, to, n=ts)
        if not is_inside_map(tx, ty):
            return (None, None)
        t = cannonball_time(sx, sy, tx, ty)
        if x == t:
            return (tx, ty)
    
    return (None, None)

#scan forward, returns (dist, entity)
def ray_cast_from_ship(ship_id):
    dist = 0
    for point in line_of_sight(ship_id):
        dist += 1
        if dist == 1:
            continue
        ent = entity_at_point(point[0], point[1])
        if ent is not None:
            return (dist - 1, ent)
    return (dist - 1, None)

#returns a list of points from (sx, sy) in direction o to the edge of the map
def line_of_sight(ship_id):
    sx = ENTITIES[ship_id]["x"]
    sy = ENTITIES[ship_id]["y"]
    o = ENTITIES[ship_id]["orient"]
    point = None
    while point is None or is_inside_map(point[0], point[1]):
        if point is not None:
            point = neighbor(point[0], point[1], o, n=1)
        else:
            point = neighbor(sx, sy, o, n=1)
        
        yield point
    
#returns the next command that will move us closer to this point
def move_to_point(id, tx, ty):
    ship = ENTITIES[id]
    
    sx, sy, ss, so = (ship["x"], ship["y"], ship["speed"], ship["orient"])
    debug("move_to_point {}: ({},{}) -> ({},{})".format(id, sx, sy, tx, ty))
    
    #we are here
    if (tx, ty) in coords_of_ship(id):
        return None
        
    #simulate the move
    nx, ny = neighbor(sx, sy, so, n=ss)
    
    #will we be there in the next move?
    if (tx, ty) in fwd_back(nx, ny, so):
        return "WAIT"
        
    #can we turn and be there in the next move?
    if (tx, ty) in fwd_back(nx, ny, (so+1)%6):
        return "PORT"
        
    #can we turn and be there in the next move?
    if (tx, ty) in fwd_back(nx, ny, (so-1)%6):
        return "STARBOARD"
        
    #so nothing in the next move..
    
    #if we are not moving
    if ss == 0:
        #turn towards target
        ang = angle(sx, sy, tx, ty)
        turn, steps = turn_to_point(so, ang)
        if turn is not None:
            return turn
        else:
            return "FASTER"
    #if we are moving slowly
    if ss == 1:
        #supose we've already moved
        sx, sy = neighbor(sx, sy, so, n=1)
        
        #are we still headed in the right direction?
        ang = angle(sx, sy, tx, ty)
        turn, steps = turn_to_point(so, ang)
        
        if turn is not None:
            return turn
            
        #how many more steps in this direction?
        steps_forward = steps_in_initial_direction_to_point(sx, sy, tx, ty)
        if steps_forward >= 2:
            return "FASTER"
        else:
            return "WAIT"
    if ss == 2:
        #supose we've already moved
        sx, sy = neighbor(sx, sy, so, n=2)
        
        #are we still headed in the right direction?
        ang = angle(sx, sy, tx, ty)
        turn, steps = turn_to_point(so, ang)
        
        if turn is not None:
            return turn
            
        #how many more steps in this direction?
        steps_forward = steps_in_initial_direction_to_point(sx, sy, tx, ty)
        if steps_forward < 3:
            return "SLOWER"
        else:
            return "WAIT"
        
    
    return "WAIT"
        
#returns the command that will steer us towards the desired direction
def turn_to_point(so, to):
    so = int(so) if so % 1 < .5 else int(so) + 1
    to = int(to) if to % 1 < .5 else int(to) + 1
    if so == 6:
        so = 0
    if to == 6:
        to = 0
    if so == to:
        return (None, 0)
    for x in [1, 2, -1, -2]:
        no = (so + x) % 6
        if no == to:
            if x > 0:
                return ("PORT", x)
            else:
                return ("STARBOARD", abs(x))
    return ("PORT", 3)
    
def steps_in_initial_direction_to_point(sx, sy, tx, ty):
    #get the initial angle
    ang = angle(sx, sy, tx, ty)
    #and round it to nearest whole
    ang = int(ang) if ang % 1 < .5 else int(ang) + 1
    ang = 0 if ang == 6 else ang
    
    new_ang = ang
    steps = 0
    while True:
        sx, sy = neighbor(sx, sy, ang, n=1)
        new_ang = angle(sx, sy, tx, ty)
        new_ang = int(new_ang) if new_ang % 1 < .5 else int(new_ang) + 1
        new_ang = 0 if new_ang == 6 else new_ang
    
        if new_ang == ang:
            steps += 1
        else:
            break
        
    return steps
    
#return list of coords [(front), (center), (rear)]
def coords_of_ship(x):
    s = ENTITIES[x]
    sx = s["x"]
    sy = s["y"]
    if s["type"] != "SHIP":
        return [(sx, sy)]
    so = s["orient"]
    return fwd_back(sx, sy, so)
    #return [neighbor(sx, sy, so), (sx, sy), neighbor(sx, sy, (so-3)%6)]
    
def fwd_back(x, y, o):
    return [neighbor(x, y, o), (x, y), neighbor(x, y, (o-3)%6)]
    
#return a list of ships
def ships():
    return [x for x in ENTITIES.values() if x["type"] == "SHIP"]

#return a list of my ships
def my_ships():
    return [x for x in ships() if x["mine"] == 1]

#return a list of computer ships
def not_my_ships():
    return [x for x in ships() if x["mine"] == 0]

#return a list of barrels
def barrels():
    return [x for x in ENTITIES.values() if x["type"] == "BARREL"]

#return a list of cannonballs
def cannonballs():
    return [x for x in ENTITIES.values() if x["type"] == "CANNONBALL"]
  
#return a list of mines 
def mines():
    return [x for x in ENTITIES.values() if x["type"] == "MINE"]

#true if ship can shoot a cannonball 
def can_shoot(ship_id):
    return loop_counter - LAST_CANNONBALL[ship_id] > CANNONBALL_COOLDOWN

#true if ship can lay a mine
def can_lay(ship_id):
    return loop_counter - LAST_MINE[ship_id] > MINE_COOLDOWN
    
#get the score of the game
def score():
    return (sum(x["rum"] for x in my_ships()), sum(x["rum"] for x in not_my_ships()))
    
#return the highest rum count for each team
def max_team_rum():
    me = max(my_ships(), key=lambda x:x["rum"])["rum"]
    you = max(not_my_ships(), key=lambda x:x["rum"])["rum"]
    return (me, you)
    
def is_safe_movement(id, cmd):
    #all the useful stuff
    ship = ENTITIES[id]
    sx = ship["x"]
    sy = ship["y"]
    so = ship["orient"]
    ss = ship["speed"]
    
    #did we alter our speed?
    if cmd is not None and "SLOWER" in cmd:
        ss -= 1
    if cmd is not None and "FASTER" in cmd:
        ss += 1
    if ss < 0:
        ss = 0
    if ss > 2:
        ss = 2
    
    #the ship moves
    sx, sy = neighbor(sx, sy, so, n=ss)
    
    if not is_inside_map(sx, sy):
        return False
        
    #get the bow and stern
    sxb, syb = neighbor(sx, sy, so)
    sxs, sys = neighbor(sx, sy, (so+3)%6)
    
    #coords of ship
    sc = [(sx, sy), (sxb, syb), (sxs, sys)]
    
    #if were going fast, then also consider one spot in front, time to slow down
    if ss == 2:
        sc.append(neighbor(sxb, syb, so))
    
    #if the ship rotates
    if cmd is not None and ( "PORT" in cmd or "STARBOARD" in cmd ):
        #update the rotation
        if "PORT" in cmd:
            so += 1
        else:
            so -= 1
        so = so % 6
        
        #get the new bow and stern
        sxb, syb = neighbor(sx, sy, so)
        sxs, sys = neighbor(sx, sy, (so+3)%6)
        
        #if we turn to face a mine, then.. no.
        fx, fy = neighbor(sxb, syb, so)
        eat = entity_at_point(fx, fy)
        if eat is not None and eat["type"] == "MINE":
            return False
        
        #update coords of ship
        sc.extend([(sxb, syb), (sxs, sys)])
        
        #if were going fast, then also consider one spot in front
        if ss == 2:
            sc.append(neighbor(sxb, syb, so))
    
    #see if there is a collision with a mine
    mine_coords = [(m["x"], m["y"]) for m in mines()]
    mine_collision = any(e in sc for e in mine_coords)
    
    #see if there is a collision with a cannonball that is about to hit
    ball_coords = [(m["x"], m["y"]) for m in cannonballs() if m["time"] <= 3]
    ball_collision = any(e in [(sx,sy),(sxb,syb),(sxs,sys)] for e in ball_coords)
    
    #see if there is a collision with a ship that isn't our own
    ship_coords = [coords_of_ship(m["id"]) for m in ships() if m["id"] != id]
    ship_collision = any(e in sc for x in ship_coords for e in x)
    
    #is there a mine exploding beside us in the next turn?
    for mine in mines():
        for cb in cannonballs():
            if (mine["x"], mine["y"]) == (cb["x"], cb["y"]) and cb["time"] == 1:
                #is this exploding mine beside us?
                if dist(mine["x"], mine["y"], sxb, syb) == 1 or dist(mine["x"], mine["y"], sxs, sys) == 1:
                    return False
        
    safe = not ( mine_collision or ball_collision or ship_collision )
    
    return safe

# game loop
loop_counter = 0
while True:
    ENTITIES = {}
    
    my_ship_count = int(input())  # the number of remaining ships
    entity_count = int(input())  # the number of entities (e.g. ships, mines or cannonballs)
    
    #loop through all of the different entities on the map
    for i in range(entity_count):
        entity_id, entity_type, x, y, arg_1, arg_2, arg_3, arg_4 = input().split()
        entity_id = int(entity_id)
        x = int(x)
        y = int(y)
        arg_1 = int(arg_1)
        arg_2 = int(arg_2)
        arg_3 = int(arg_3)
        arg_4 = int(arg_4)
        
        #create the entity dict for reference
        entity = {"id":entity_id, "type":entity_type, "x":x, "y":y}
        if entity_type == "SHIP":
            entity.update({"orient":arg_1, "speed":arg_2, "rum":arg_3, "mine":arg_4})
        elif entity_type == "BARREL":
            entity.update({"rum":arg_1})
        elif entity_type == "CANNONBALL":
            entity.update({"owner":arg_1, "time":arg_2})
        elif entity_type == "MINE":
            #keep track of all the mines we've seen
            if entity not in mines_seen:
                mines_seen.append(entity)
        
        #store these for future computation
        ENTITIES[entity_id] = entity

    #make sure we remove any mines_seen if they aren't there anymore
    for mine in mines_seen:
        #if there is a ship that could see this mine
        for ship in my_ships():
            if dist(mine["x"], mine["y"], ship["x"], ship["y"]) <= 5:
                #but it wasn't in the entities
                if mine not in mines() and mine in mines_seen:
                    mines_seen.remove(mine)
    #if any cannonballs are above a mine, then remove the mine
    for mine in mines_seen:
        for cb in cannonballs():
            if (mine["x"], mine["y"]) == (cb["x"], cb["y"]) and mine in mines_seen:
                mines_seen.remove(mine)
    #if any ships are over a mine, then remove the mine
    for mine in mines_seen:
        for ship in ships():
            if (mine["x"], mine["y"]) in coords_of_ship(ship["id"]) and mine in mines_seen:
                mines_seen.remove(mine)
                
    
    #if we like to see the output
    #for e in ENTITIES.values():
    #    debug(e)
    
    MY_SHIP_IDS = [s["id"] for s in my_ships()]
    COMPUTER_SHIP_IDS = [s["id"] for s in not_my_ships()]
    
    #keep track of my ships this frame
    prev_ship.append({})
    for MY_SHIP_ID in MY_SHIP_IDS:
        #first time, initialize the action variables
        if loop_counter == 0:
            LAST_CANNONBALL[MY_SHIP_ID] = -10
            LAST_MINE[MY_SHIP_ID] = -10
            action[MY_SHIP_ID] = None
        
        if action[MY_SHIP_ID] is not None:
            continue
        
        MY_SHIP = ENTITIES[MY_SHIP_ID]
        
        near_alli = sorted([x for x in my_ships() if x["id"] != MY_SHIP_ID], key=lambda x:
            dist(MY_SHIP["x"],MY_SHIP["y"],x["x"],x["y"]))
        near_barrels = sorted(barrels(), key=lambda x:
            dist(MY_SHIP["x"],MY_SHIP["y"],x["x"],x["y"]))
        near_enemy = sorted(not_my_ships(), key=lambda x:
            dist(MY_SHIP["x"],MY_SHIP["y"],x["x"],x["y"]))
        
        my_score, your_score = score()
        my_high, your_high = max_team_rum()
        
        mssx, mssy = coords_of_ship(MY_SHIP_ID)[2]
        enemy_behind = entity_at_point(mssx, mssy)
        
        dist_to_enemy = dist(MY_SHIP["x"], MY_SHIP["y"], near_enemy[0]["x"], near_enemy[0]["y"])
        if len(near_alli) > 0:
            dist_to_alli = dist(MY_SHIP["x"], MY_SHIP["y"], near_alli[0]["x"], near_alli[0]["y"])
        
        #we are hungry
        if len(near_barrels) > 0 and ( MY_SHIP["rum"] < 90 or MY_SHIP["rum"] < your_high ):
            action[MY_SHIP_ID] = move_to_point(MY_SHIP_ID, near_barrels[0]["x"], near_barrels[0]["y"])
    
        elif len(near_alli) > 0 and len(near_barrels)==0 and MY_SHIP["rum"] < 30 and your_high > my_high and dist_to_alli < dist_to_enemy - 2:
            if MY_SHIP["speed"] > 0:
                action[MY_SHIP_ID] = "SLOWER"
            else:
                action[MY_SHIP_ID] = "FIRE {} {}".format(MY_SHIP["x"], MY_SHIP["y"])
            
            action[near_alli[0]["id"]] = move_to_point(near_alli[0]["id"], MY_SHIP["x"], MY_SHIP["y"])
        #shoot at an enemy
        else:
            #sneaky shoot a mine from mines_seen
            for enemy in near_enemy:
                for ex, ey in coords_of_ship(enemy["id"]):
                    for mine in mines_seen:
                        if dist(ex, ey, mine["x"], mine["y"]) == 1 and shooting_distance(MY_SHIP_ID, mine["x"], mine["y"]) <= 10:
                            ex, ey = neighbor(ex, ey, enemy["orient"], n=enemy["speed"])
                            if dist(ex, ey, mine["x"], mine["y"]) == 1:
                                action[MY_SHIP_ID] = "FIRE {} {} blindside!".format(mine["x"], mine["y"])
                                break
            else:
                enemy = near_enemy[0]
                enemy_dist = dist(MY_SHIP["x"], MY_SHIP["y"], enemy["x"], enemy["y"])
                if enemy_dist > 10:
                    action[MY_SHIP_ID] = move_to_point(MY_SHIP_ID, enemy["x"], enemy["y"])
                
        #override waiting with a cannonball shot
        if action[MY_SHIP_ID] in [None, "WAIT"] and can_shoot(MY_SHIP_ID):
            for enemy in not_my_ships():
                pass
            enemy = near_enemy[0]
            px, py = cannonball_predict(MY_SHIP["x"], MY_SHIP["y"], enemy["id"])
            if px is not None:
                bx, by = coords_of_ship(MY_SHIP_ID)[0]
                act = "FIRE {} {}".format(px, py)
                if dist(bx, by, px, py) <= 10:
                    if "FIRE" not in ''.join([x if x is not None else '' for x in action.values()]):
                        action[MY_SHIP_ID] = act
                    else:
                        ang = angle(px,py,bx,by)
                        ang = round(ang)
                        ang = 0 if ang == 6 else ang
                        px, py = neighbor(px,py,ang)
                        action[MY_SHIP_ID] = "FIRE {} {}".format(px, py)
            
        
        #are we stuck for the last 2 frames?
        stuck = True
        for o in prev_ship[-3:-1]:
            if not (o[MY_SHIP_ID]["x"] == MY_SHIP["x"] and o[MY_SHIP_ID]["y"] == MY_SHIP["y"] and o[MY_SHIP_ID]["orient"] == MY_SHIP["orient"]):
                stuck = False
                break
            
        if len(prev_ship) > 2 and stuck:
            acts = ["PORT", "STARBOARD", "FASTER"]
            acts = [a for a in acts if action[MY_SHIP_ID] not in acts and is_safe_movement(MY_SHIP_ID, a)]
            
            if len(acts) > 0:
                random.shuffle(acts)
                action[MY_SHIP_ID] = acts[0]
            else:
                action[MY_SHIP_ID] = random.choice(["PORT", "STARBOARD"])
        
    #write out the actions for each ship
    debug(" --- ")
    for MY_SHIP_ID in MY_SHIP_IDS:
        MY_SHIP = ENTITIES[MY_SHIP_ID]
        
        debug("{}: i:{}, s:{}".format(MY_SHIP_ID, action[MY_SHIP_ID], is_safe_movement(MY_SHIP_ID, action[MY_SHIP_ID])))
        
        if not is_safe_movement(MY_SHIP_ID, action[MY_SHIP_ID]):
            acts = ["PORT", "STARBOARD", "FASTER", "SLOWER", "WAIT"]
            if MY_SHIP["speed"] == 2:
                acts.remove("FASTER")
            if MY_SHIP["speed"] == 0:
                acts.remove("SLOWER")
                
            acts = [a for a in acts if is_safe_movement(MY_SHIP_ID, a)]
            debug("{}: safe:{}".format(MY_SHIP_ID, acts))
            if len(acts) == 0:
                if MY_SHIP["speed"] < 2:
                    if prev_action[MY_SHIP_ID] == "FASTER":
                        action[MY_SHIP_ID] = "PORT"
                    else:
                        action[MY_SHIP_ID] = "FASTER"
                else:
                    action[MY_SHIP_ID] = "SLOWER"
            else:
                action[MY_SHIP_ID] = random.choice(acts)
                
                    
        debug("{}: a:{}, s:{}".format(MY_SHIP_ID, action[MY_SHIP_ID], is_safe_movement(MY_SHIP_ID, action[MY_SHIP_ID])))
        
        if action[MY_SHIP_ID] is None:
            action[MY_SHIP_ID] = "SLOWER"
            
        print(action[MY_SHIP_ID])
        
        #update cooldowns
        if "FIRE" in action[MY_SHIP_ID]:
            LAST_CANNONBALL[MY_SHIP_ID] = loop_counter
        if "MINE" in action[MY_SHIP_ID]:
            LAST_MINE[MY_SHIP_ID] = loop_counter
            
        prev_action[MY_SHIP_ID] = action[MY_SHIP_ID]
        prev_ship[loop_counter][MY_SHIP_ID] = MY_SHIP
        
        action[MY_SHIP_ID] = None
            
    loop_counter += 1