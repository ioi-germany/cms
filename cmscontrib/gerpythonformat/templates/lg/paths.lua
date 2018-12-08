function simple_copy(t)
    if t == nil then
        return nil
    end

    local r = {}
    
    for key, val in pairs(t) do
        if type(val) == 'table' then
            r[key] = simple_copy(val)
        else
            r[key] = val
        end
    end
    
    return setmetatable(r, getmetatable(t))
end


Vector = {}
Vector.__index = Vector

function Vector:new(x,y)
    local v = {}
    setmetatable(v, Vector)
    
    v.x = x
    v.y = y
    
    return v
end

function Vector.__add(v, w)
    return Vector:new(v.x + w.x, v.y + w.y)
end

function Vector.__sub(v, w)
    return Vector:new(v.x - w.x, v.y - w.y)
end

function Vector.__mul(f, v)
    return Vector:new(f*v.x, f*v.y)
end

function Vector.__div(v, f)
    return Vector:new(v.x/f, v.y/f)
end

function Vector.__unm(v)
    return Vector:new(-v.x, -v.y)
end

function Vector:len()
    return math.sqrt(self.x^2 + self.y^2)    
end

function Vector:normal()
    return Vector:new(-self.y, self.x)
end

function Vector:unit_normal()
    return self:normal() / self:len()
end

function Vector:angle()
    return math.atan2(self.y, self.x)
end

function Vector:tikz_repr()
    return string.format("(%.5fpt, %.5fpt)", self.x, self.y)
end

function Vector:copy()
    return Vector:new(self.x, self.y)
end


Rectangle = {}
Rectangle.__index = Rectangle

function Rectangle:new(sw, ne)
    local r = {}
    setmetatable(r, Rectangle)
    
    r.sw = sw:copy()
    r.ne = ne:copy()
    
    return r
end

function Rectangle:bound(...)
    local args = {...}

    if #args == 0 then
        error("can't bound empty list")
    end
    
    local r = Rectangle:new(args[1], args[1])

    for i,v in ipairs(args) do           
        if v.x < r.sw.x then r.sw.x = v.x end
        if v.y < r.sw.y then r.sw.y = v.y end
        
        if v.x > r.ne.x then r.ne.x = v.x end
        if v.y > r.ne.y then r.ne.y = v.y end
    end
    
    return r
end

function Rectangle:draw(style)
    style = style or ""

    tex.print("\\draw[" .. style .. " ] " .. self.sw:tikz_repr() .. " -- " ..
              Vector:new(self.sw.x, self.ne.y):tikz_repr() .. " -- " ..
              self.ne:tikz_repr() .. " -- " ..
              Vector:new(self.ne.x, self.sw.y):tikz_repr() .. " -- cycle;")
end

function Rectangle:perimeter()
    return 2 * (self.ne.y - self.sw.y + self.ne.x - self.sw.x)
end

function Rectangle:intersects(rect)
    return self.sw.x <= rect.ne.x and self.sw.y <= rect.ne.y and 
           self.ne.x >= rect.sw.x and self.ne.y >= rect.sw.y
end


BezierCurve = {}
BezierCurve.__index = BezierCurve

function BezierCurve:new(from, control_a, control_b, to)
    -- We allow to call this function with two parameters (in which case we
    -- produce a line)
    if control_b == nil and to == nil then
        to = simple_copy(control_a)
        control_a = (from + to) / 2
        control_b = (from + to) / 2
    end

    local b = {}
    setmetatable(b, BezierCurve)
    
    b.from = simple_copy(from)
    b.control_a = simple_copy(control_a)
    b.control_b = simple_copy(control_b)
    b.to = simple_copy(to)
    
    return b
end

-- Use de Casteljau's Algorithm to evaluate the curve at time t and also get
-- the control points of the two subcurves
function BezierCurve:_split(t)
    local control_a_first = t * self.control_a + (1-t) * self.from
    local control_b_second = t * self.to + (1-t) * self.control_b
    local auxiliary = t * self.control_b + (1-t) * self.control_a
    
    local control_b_first = t * auxiliary + (1-t) * control_a_first
    local control_a_second = t * control_b_second + (1-t) * auxiliary
    
    local p = t * control_a_second + (1-t) * control_b_first;
    
    return BezierCurve:new(self.from, control_a_first, control_b_first, p),
           BezierCurve:new(p, control_a_second, control_b_second, self.to)
end

function BezierCurve:at_time(t)
    local a, b = self:_split(t)
    return a.to
end

function BezierCurve:tangent_at_time(t)
    local a, b = self:_split(t)
    local t = b.control_a - b.from
    
    if t:len() == 0 then
        return t
    else
        return t / t:len()
    end
end

function BezierCurve:normal_at_time(t)
    return self:tangent_at_time(t):normal()
end

function BezierCurve:sub(t0, t1)
    if t0 == 1 then
        return BezierCurve:new(self.to, self.to, self.to, self.to)
    end
     
    local _, a = self:_split(t0)
    a, _ = a:_split((t1 - t0) / (1 - t0))
    
    return a
end

function BezierCurve:split(L)
    local times = simple_copy(L)
    table.insert(times, 1)
    table.sort(times)
    
    local prev = 0
    local res = {}
    
    for _, t in ipairs(times) do
        table.insert(res, self:sub(prev, t))    
        prev = t
    end
    
    return res
end

function BezierCurve:draw(style)
    style = style or ""

    tex.print("\\draw[" .. style .. "] " .. self.from:tikz_repr() ..
              " .. controls " ..
              self.control_a:tikz_repr() .. " and " ..
              self.control_b:tikz_repr() .. " .. " ..
              self.to:tikz_repr() .. ";")
end

function BezierCurve:bounding_box()
    return Rectangle:bound(self.from, self.to, self.control_a, self.control_b)
end


TikzPath = {}
TikzPath.__index = TikzPath

function TikzPath:new()
    local t = {}
    setmetatable(t, TikzPath)
    
    t.segments = {}
    t.components = {}
    
    return t
end

function TikzPath:append(c, glue)
    table.insert(self.segments, simple_copy(c))
    
    if not glue then
        table.insert(self.components, {})
    end
    
    table.insert(self.components[#self.components], #self.segments)
end

function TikzPath:concat(p, glue)
    for i, c in ipairs(p.components) do
        if not glue or i ~= 1 then
            table.insert(self.components, {})
        end
        
        for _, s in ipairs(c) do
            table.insert(self.segments, simple_copy(p.segments[s]))
            table.insert(self.components[#self.components], #self.segments)
        end
    end
end

function TikzPath:concat_list(L, glue)
    local r = TikzPath:new()
    
    for i, p in ipairs(L) do
        r:concat(p, glue and (i ~= 1))
    end
    
    return r
end

function TikzPath:new_pl(...)
    local points = {...}
    
    local res = TikzPath:new()

    if #points == 1 then
        res:append(BezierCurve:new(points[1], points[1]))
    end    
    
    for i = 2, #points do
        res:append(BezierCurve:new(points[i - 1], points[i]))
    end
    
    return res
end

function TikzPath:from_rectangle(rect)
    return TikzPath:new_pl(rect.ne, Vector:new(rect.ne.x, rect.sw.y),
                           rect.sw, Vector:new(rect.sw.x, rect.ne.y), rect.ne)
end

function TikzPath:draw(style)
    style = style or ""
    
    tex.print("\\draw[" .. style .. "] ")
    
    for _, c in ipairs(self.components) do
        for i, s in ipairs(c) do
            local curve = self.segments[s]
        
            if i ~=1 then
                tex.print(" -- ")
            end
        
            tex.print(curve.from:tikz_repr() .. " .. controls " ..
                      curve.control_a:tikz_repr() .. " and " ..
                      curve.control_b:tikz_repr() .. " .. " ..
                      curve.to:tikz_repr())
        end
    end
    
    tex.print(";")
end

-- WARNING! If you call these functions on discontinuities (for non-contiguous
-- paths) we consider the first point of the next segment
function TikzPath:decode_time(t)
    local i, f = math.modf(t)
    
    if i == #self.segments then
        f = 1
    else
        i = i + 1
    end
    
    return i, f
end

function TikzPath:at_time(t)
    local i, f = self:decode_time(t)
    return self.segments[i]:at_time(f)
end

function TikzPath:tangent_at_time(t)
    local i, f = self:decode_time(t)
    return self.segments[i]:tangent_at_time(f)
end

function TikzPath:normal_at_time(t)
    local i, f = self:decode_time(t)
    return self.segments[i]:normal_at_time(f)
end

function TikzPath:sub(t0, t1)
    local res = TikzPath:new()
    
    local first_segment, t0_f = math.modf(t0)
    first_segment = first_segment + 1
    
    local second_segment, t1_f = math.modf(t1)
    second_segment = second_segment + 1
    
    if t1_f == 0 and second_segment > first_segment then
        second_segment = second_segment - 1
        t1_f = 1
    end

    for _, c in ipairs(self.components) do
        local pushed = false
    
        for _, s in ipairs(c) do
            if s >= first_segment and s <= second_segment then
                if not pushed then
                    table.insert(res.components, {})
                end
                
                local curr_t0 = 0
                local curr_t1 = 1
                
                if s == first_segment then curr_t0 = t0_f end
                if s == second_segment then curr_t1 = t1_f end
                
                local c = self.segments[s]:sub(curr_t0, curr_t1)
                
                table.insert(res.segments, c)
                table.insert(res.components[#res.components], #res.segments)                
                
                pushed = true
            end
        end
    end

    return res
end

function TikzPath:split(L)
    local times = simple_copy(L)
    table.insert(times, #self.segments)
    table.sort(times)
    
    local prev = 0
    local res = {}
    
    for _, t in ipairs(times) do
        table.insert(res, self:sub(prev, t))
        prev = t
    end
    
    return res
end

function TikzPath:arc_time_to_time(t)
    local NUM_SAMPLES = 500
    
    local l = {}
    local prev = self:at_time(0)
    
    l[0] = 0
    
    for i = 1, NUM_SAMPLES * #self.segments do
        local curr = self:at_time(i / NUM_SAMPLES)
        l[i] = l[i - 1] + (curr - prev):len()
        prev = curr
    end
    
    local arc_length = l[NUM_SAMPLES * #self.segments]
    
    for i = 0, NUM_SAMPLES * #self.segments do
        if l[i] >= t * arc_length then
            return i / NUM_SAMPLES
        end
    end
    
    return #self.segments
end

function TikzPath:mid_time()
    return self:arc_time_to_time(.5)
end

-- Do not call this function yourself!
-- TODO: catch case of infinitely many intersections
function _intersect(a, b, TOLERANCE, MAX_DEPTH)
    local base_curves = {a, b}

    local res = {}
    
    local stack = {}    
    table.insert(stack, {depth = 0, times = {{l = 0, r = 1}, {l = 0, r = 1}}})
    
    repeat
        local curr = simple_copy(stack[#stack])
        stack[#stack] = nil
        
        local bb_a = a:sub(curr.times[1].l, curr.times[1].r):bounding_box()
        local bb_b = b:sub(curr.times[2].l, curr.times[2].r):bounding_box()
        
        if bb_a:perimeter() <= TOLERANCE and bb_b:perimeter() <= TOLERANCE then
            table.insert(res, {first = (curr.times[1].l + curr.times[1].r) / 2,
                              second = (curr.times[2].l + curr.times[2].r) / 2})

            if #res > 100 then
                print("Warning! Non-generic intersection! " ..
                      "I will ignore some (i.e. infinitely many) " ..
                      "intersection points...")
                return {}
            end
        elseif curr.depth < MAX_DEPTH then
            local rec = {}
            
            for i, t in ipairs(curr.times) do
                local c = base_curves[i]:sub(t.l, t.r)
                local m = (t.l + t.r) / 2
            
                if c:bounding_box():perimeter() > TOLERANCE and m > t.l
                                                            and m < t.r then
                    table.insert(rec, {{l = t.l, r = m}, {l = m, r = t.r}})
                else
                    table.insert(rec, {{l = t.l, r = t.r}})
                end
            end
                    
            for _, first in ipairs(rec[1]) do
                for _, second in ipairs(rec[2]) do
                    local r1 = a:sub(first.l, first.r):bounding_box()
                    local r2 = b:sub(second.l, second.r):bounding_box()
                
                    if r1:intersects(r2) then
                        table.insert(stack, {depth = curr.depth + 1, 
                                             times = {simple_copy(first), 
                                                      simple_copy(second)}})
                    end
                end
            end        
        else
            error("too imprecise")
        end       
    until #stack == 0
    
    return res
end

function TikzPath:intersect(other)
    local TOLERANCE = 1e-3
    local MAX_DEPTH = 30
    local EPSILON = 1e-6
    
    local pre = {}
    
    for i, a in ipairs(self.segments) do
        for j, b in ipairs(other.segments) do
            for _, t in ipairs(_intersect(a, b, TOLERANCE, MAX_DEPTH)) do
                local p = a:at_time(t.first)
            
                -- "handle" intersections at discontinuities
                -- (note that p is always correct)
                if t.first >= 1 then
                    t.first = 1 - EPSILON
                end
                
                if t.second >= 1 then
                    t.second = 1 - EPSILON
                end
            
                table.insert(pre, {first = (i - 1) + t.first,
                                   second = (j - 1) + t.second,
                                   point = p})
            end
        end
    end
    
    table.sort(pre, function(x, y)
                        if x.first < y.first then return true end
                        if x.first > y.first then return false end
                        
                        return x.second < y.second
                    end)
    
    local prev = nil
    local res = {}
    
    for _, t in ipairs(pre) do
        -- TODO: handle triple points
        if prev == nil or (prev.point - t.point):len() > 2 * TOLERANCE then
            table.insert(res, simple_copy(t))
        end
        
        prev = simple_copy(t)
    end
    
    return res
end

function TikzPath:thicken(time, r)
    local p = self:at_time(time)
    local t = 3 * self:tangent_at_time(time)
    local n = self:normal_at_time(time)
        
    return TikzPath:new_pl(p - r * t + r * n, 
                           p - r * t - r * n, 
                           p + r * t - r * n,
                           p + r * t + r * n, 
                           p - r * t + r * n)
end

-- TODO (?): the whole method assumes there are no triple intersections (i.e. 
-- intersections with self intersections of the other path)
function TikzPath:split_along(path)    
    local res = {}
    local intersections = self:intersect(path)
    
    local prev = {first = 0, second = 0}
    
    for i, t in ipairs(intersections) do
        local c = self:sub(prev.first, t.first)        
        table.insert(res, c)
        prev = simple_copy(t)
    end
    
    local c = self:sub(prev.first, #self.segments)
    
    table.insert(res, c)    
    return res
end

function TikzPath:gap(_obstacles)
    local obstacles = simple_copy(_obstacles)
    table.sort(obstacles, function(x, y) return x.time < y.time end)
    
    local segments = {}
    local prev = 0
    
    for i, o in ipairs(obstacles) do
        local curr_center = o.time
        local intersections = self:intersect(o.gap)
        
        local last_before = nil
        local first_after = nil
        
        for _, inter in ipairs(intersections) do
            if inter.first < curr_center then
                last_before = inter.first
            else
                first_after = inter.first
                break
            end
        end
       
        table.insert(segments, self:sub(prev, last_before))
        
        prev = first_after
    end
    
    if prev then
        table.insert(segments, self:sub(prev, #self.segments))
    end
    
    return TikzPath:concat_list(segments)
end

function TikzPath:circle(c, r)
    local res = TikzPath:new()
    
    table.insert(res.components, {1, 2, 3, 4})
    
    local o = {Vector:new(1,0), Vector:new(0,1),
               Vector:new(-1,0), Vector:new(0,-1)}
    
    for i = 1,4 do
        table.insert(res.segments,
                     BezierCurve:new(c + r * o[i],
                                     c + r * o[i] + .552 * r * o[i % 4 + 1],
                                     c + r * o[i % 4 + 1] + .552 * r * o[i],
                                     c + r * o[i % 4 + 1]))
    end
    
    return res
end

function TikzPath:shorten_start(by)
    if #self.segments == 0 then
        return TikzPath:new()
    end

    local intersections = self:intersect(by)
    
    if #intersections == 0 then
        return TikzPath:new()
    else
        return self:sub(intersections[#intersections].first, #self.segments)
    end
end

function TikzPath:shorten_end(by)
    if #self.segments == 0 then
        return TikzPath:new()
    end
    
    local intersections = self:intersect(by)

    if #intersections == 0 then
        return TikzPath:new()
    else    
        return self:sub(0, intersections[1].first)
    end
end


function extract_dim(s)
    if s:sub(-2) ~= "pt" then
        error("I expected this to end in pt (not fire)")
    end
        
    return tonumber(s:sub(1, s:len() - 2))
end


-- The following are auxiliary methods for the passpathtolua macro (that does
-- exactly what it says on the tin); don't use them on your own unless you
-- know what you're doing...
function _move(x, y)
    __curr_pos = Vector:new(extract_dim(x), extract_dim(y))
    __moved = true
end

function _line(x, y)
    local new_pos = Vector:new(extract_dim(x), extract_dim(y))
    __curr_path:append(BezierCurve:new(__curr_pos, new_pos), not __moved)
    
    __curr_pos = new_pos
    __moved = false
end

function _curve_supp_a(x, y)
    __supp_a = Vector:new(extract_dim(x), extract_dim(y))
end

function _curve_supp_b(x, y)
    __supp_b = Vector:new(extract_dim(x), extract_dim(y))
end

function _curve(x,y)
    local new_pos = Vector:new(extract_dim(x), extract_dim(y))
    __curr_path:append(BezierCurve:new(__curr_pos, __supp_a, __supp_b, new_pos), 
                       not __moved)
    
    __curr_pos = new_pos
    __moved = false
end
