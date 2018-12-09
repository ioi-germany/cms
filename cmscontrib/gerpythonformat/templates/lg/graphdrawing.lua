require("paths.lua")

function parse_args(s)
    local r = {}
    
    local token = ""
    local argname = ""
    local valued = false
    
    for c in s:gmatch(".") do
        if c == ',' then        
            if valued then
                r[argname] = tonumber(token)
            else
                r[token] = true
            end
            
            valued = false
            token = ""
        elseif c == '=' then
            argname = token
            token = ""
            valued = true
        elseif c ~= ' ' then
            token = token .. c    
        end
    end
    
    if valued then
        r[argname] = tonumber(token)
    else
        r[token] = true
    end
    
    return r
end


Annotation = {}
Annotation.__index = Annotation

function Annotation:new(text)
    local a = {}

    a.text = text
    a.rect = {}
    
    return a
end


Node = {}
Node.__index = Node

function Node:new(text)
    local n = {}
    setmetatable(n, Node)
    
    n.text = text
    n.annotations = {}
    n.markings = {}
    
    return n
end

function Node:annotate(text)
    table.insert(self.annotations, Annotation:new(text))
end


Edge = {}
Edge.__index = Edge

function Edge:new(from, to, directed, label)
    local e = {}
    setmetatable(e, Edge)
    
    e.from = from
    e.to = to
    e.directed = directed
    e.label = label
    
    return e
end


Graph = {}
Graph.__index = Graph
Graph.instances = {}

function Graph:new(param_string, file_name)
    local g = {}
    setmetatable(g, Graph)
    
    g.args = {--graph and input parameters
              directed=false,
              tree=false,
              weighted=false,
              annotated=false,
              zero_based=false,
              markings=0,
              skip=0,
              skip_before=0,
              
              -- styling parameters
              bend_amount = 25,
              follow_edges = false,
              
              -- additional parameters for TikZ's graph drawing algorithms
              node_distance = nil,
              random_seed = 42}
    
    for key, value in pairs(parse_args(param_string)) do
        g.args[key] = value
    end
    
    local f = io.open(file_name)
    
    -- skip entries if necessary
    for i = 1, g.args.skip_before do f:read("*number") end
    
    g.N = f:read("*number")
    g.M = g.N - 1
    
    if not g.args.tree then
        g.M = f:read("*number")
    end
    
    -- skip entries if necessary
    for i = 1, g.args.skip do f:read("*number") end
    
    -- create nodes
    g.nodes = {}
        
    g.first_node_id = 1
    g.first_edge_id = 1
    
    if g.args.zero_based then
        g.first_node_id = 0
        g.first_edge_id = 0
    end
    
    for i = g.first_node_id, g.first_node_id + g.N - 1 do
        g.nodes[i] = Node:new("$" .. tostring(i) .. "$")
    end
    
    -- read markings if necessary
    local num_markings = {}
    
    for i = 1, g.args.markings do
        table.insert(num_markings, f:read("*number"))
    end
        
    for i = 1, g.args.markings do
        for _ = 1, num_markings[i] do
            table.insert(g.nodes[f:read("*number")].markings, i)
        end
    end

    
    -- read annotations if necessary
    if g.args.annotated then
        for i = g.first_node_id, g.first_node_id + g.N - 1 do
            g.nodes[i]:annotate("$" .. tostring(f:read("*number")) .. "$")
        end
    end
    
    -- read edges (including weights, if necessary)
    g.edge_table = {}
    g.edge_list = {}
    
    for i = g.first_edge_id, g.first_edge_id + g.M - 1 do
        local u, v = f:read("*number", "*number")
        
        local weight = ""
        
        if g.args.weighted then
            weight = "$\\scriptstyle " .. tostring(f:read("*number")) .. "$"
        end
        
        local e = Edge:new(u, v, g.args.directed, weight)
        
        g.edge_table[u] = g.edge_table[u] or {}
        g.edge_table[u][v] = g.edge_table[u][v] or {}
        
        g.edge_list[i] = e
        table.insert(g.edge_table[u][v], i)
    end
    
    g.directed = g.args.directed
    
    table.insert(Graph.instances, g)
    g.id = #Graph.instances
    Graph.curr_instance = g.id
    
    return g
end

function Graph:ctx_eval(expr)
    local r, err = load("return " .. expr, "Graph:ctx_eval", "t", 
                        {N = self.N, M = self.M})

    if r == nil and err ~= nil then
        error(err)
    end
    
    return r()
end

function Graph:mark_node(idx, m)
    table.insert(self.nodes[self:ctx_eval(idx)].markings, self:ctx_eval(m))
end

function store_tikz_point_deferred(pointname, varname)
    tex.print("\\begin{scope}")
    tex.print("\\tikzmath{coordinate \\p; \\p = (" .. pointname .. ");};")
    tex.print("\\directlua{" .. varname .. " = " ..
              "Vector:new(extract_dim(\"\\px\"), extract_dim(\"\\py\"))}")
    tex.print("\\end{scope}")
end

function Graph:_add_edge_path(from, to, path)
    from = tonumber(from:sub(2))
    to = tonumber(to:sub(2))

    for _, ref in ipairs(self.edge_table[from][to]) do
        local e = self.edge_list[ref]
        
        if not e.path then
            e.path = path
            return
        end
    end
end

-- this function has to be called while inside some TikZ environment!
function Graph:basic_layout()
    -- The macro saveedgepath will be called automatically later on each edge
    -- once it has been routed
    tex.print("\\def\\saveedgepath#1#2{\\directlua{Graph.instances[" ..
              tostring(self.id) ..
              "]:_add_edge_path(\"#1\", \"#2\", __curr_path)}}")

    -- Let us first draw the graph via TikZ' graph drawing capabilities
    local additional_options = ""
    
    if self.args.node_distance ~= nil then
        additional_options = additional_options .. ", node distance=" ..
                             tostring(self.args.node_distance) .. "pt"
    end

    tex.print("\\graph[random seed = " .. tostring(self.args.random_seed) ..
                       "," .. "spring electrical layout, " ..
                       "approximate remote forces = false, " ..
                       "convergence tolerance = 0, " ..
                       "iterations=500, " ..
                       "downsize ratio=0.5, " ..
                       "nodes={circle,draw, inner sep=.2em, " ..
                              "minimum size=1.9em}," ..
                       "component align=counterclockwise" .. 
                       additional_options .. 
                       "]{")

    for i = self.first_node_id, self.first_node_id + self.N - 1 do
        local n = self.nodes[i]
        local label = ""
        
        for _, a in ipairs(n.annotations) do
            label = ", label={[name=a" .. i ..  ",annotation] above right: " ..
                    a.text .. "}"
        end
        
        local markings = ""
        
        for _, m in ipairs(n.markings) do
            markings = markings .. ", marking " .. tostring(m)
        end

        tex.print("v" .. tostring(i) .. " [as = " .. n.text .. label .. 
                  markings .. "];")
    end
    
    for u = self.first_node_id, self.first_node_id + self.N - 1 do
        if self.edge_table[u] then
            for v = self.first_node_id, self.first_node_id + self.N - 1 do
                for id, ref in ipairs(self.edge_table[u][v] or {}) do
                    local e = self.edge_list[ref]
                    
                    local bending = ""
        
                    if #(self.edge_table[u][v]) > 1 or (self.edge_table[v] and
                                                        self.edge_table[v][u])
                       then
                        bending = "bend left=" ..
                                      tostring((id - .5) * 
                                               self.args.bend_amount) .. "pt"

                        e.fixed_normal = true
                    end
                        
                    tex.print("v" .. tostring(u) .. "" .. "--[draw=none," ..
                              bending ..  " ]" .. " v" .. tostring(v) .. ";")
                end
            end
        end
    end
    
    tex.print("};")
    
    for i, n in pairs(self.nodes) do
        for j, a in ipairs(n.annotations) do
            local pt_name = "a" .. tostring(i) .. "."     
            local var_name = "Graph.instances[" .. tostring(self.id) .. "]." ..
                             "nodes[" .. tostring(i) .. "].annotations[" ..
                             tostring(j) .. "].rect."

            store_tikz_point_deferred(pt_name .. "north east", var_name .. "ne")
            store_tikz_point_deferred(pt_name .. "south west", var_name .. "sw")
        end
    end
end

function Graph:shorten_edges()
    for i, n in pairs(self.nodes) do
        for j, a in ipairs(n.annotations) do
            a.boundary = TikzPath:from_rectangle(a.rect)
        end
    end
   
    for i, e in pairs(self.edge_list) do
        for j, a in ipairs(self.nodes[e.from].annotations) do
            if #a.boundary:intersect(e.path) ~= 0 then
                e.path = e.path:shorten_start(a.boundary)
            end
        end
        
        for j, a in ipairs(self.nodes[e.to].annotations) do
            if #a.boundary:intersect(e.path) ~= 0 then
                e.path = e.path:shorten_end(a.boundary)
            end
        end
    end
end

function Graph:get_intersection_graph()
    -- We build the following graph: nodes are edges of the original graph and
    -- there is an edge between nodes for every intersection between these edges
    -- in the calculated edge routing
    local res = {nodes = {}, edges = {}, adj = {}}
    
    for _, e in pairs(self.edge_list) do
        table.insert(res.nodes, e)
        res.adj[#res.nodes] = {}
    end
    
    for i, e in ipairs(res.nodes) do
        for j, f in ipairs(res.nodes) do
            if i < j then                
                for _, inter in ipairs(e.path:intersect(f.path)) do
                    local x = {times = {inter.first, inter.second},
                               gaps = {f.path:thicken(inter.second, 2),
                                       e.path:thicken(inter.first, 2)}}
                
                    table.insert(res.edges, x)
                    table.insert(res.adj[i], {id = #res.edges, to = j})
                    table.insert(res.adj[j], {id = #res.edges, to = i})
                end
            end
        end
    end
    
    return res
end

function calculate_gaps(G)
    -- "Oh, what a tangled web we weave..."
    --
    -- It seems that the most aesthetically pleasing ways to choose "over/under"
    -- at crossings are those that maximize symmetries of the over/under
    -- patterns. In particular, we want to have many cycles.
    --
    -- We heuristically try to find such a choice by orienting all edges of the
    -- DFS tree downwards and all back edges upwards (in particular we will
    -- always find a cycle if one exists)
    --
    -- If we have way too much time we might also try to find an assignment that
    -- actually maximizes the number of symmetries of the resulting graph,
    -- however the naive implementation would take O(n!2^m) time...
    local res = {}
    
    for i, n in ipairs(G.nodes) do
        res[i] = {}
    end
    
    local visited = {}
        
    local function visit(v)
        visited[v] = true
    
        for _, edge_ref in ipairs(G.adj[v]) do
            local e = G.edges[edge_ref.id]
            local w = edge_ref.to
            
            local i = 1
            
            if v > w then
                i = 2
            end
            
            if not e.oriented then
                e.oriented = true
                table.insert(res[v], {time = e.times[i],  gap = e.gaps[i]})
            end
            
            if not visited[w] then
                visit(w)
            end
        end
    end
    
    for i, n in ipairs(G.nodes) do
        if not visited[i] then
            visit(i)
        end
    end
    
    return res
end

function Graph:draw_edges()
    self:shorten_edges()

    local intersection_graph = self:get_intersection_graph()
    local gaps = calculate_gaps(intersection_graph)
    
    for i, g in ipairs(gaps) do
        local e = intersection_graph.nodes[i]        
        e.gapped_path = e.path:gap(g)
    end
   
    local arrow_tip = ""
    
    if self.directed then
        arrow_tip = "->"
    end
    
    for i, e in pairs(self.edge_list) do
        e.gapped_path:draw(arrow_tip)
    end
end

function Graph:find_segments()
    for i, e in pairs(self.edge_list) do
        for j, a in ipairs(self.nodes[e.from].annotations) do
            if #a.boundary:intersect(e.path) ~= 0 then
                e.path = e.path:shorten_start(a.boundary)
            end
        end
        
        for j, a in ipairs(self.nodes[e.to].annotations) do
            if #a.boundary:intersect(e.path) ~= 0 then
                e.path = e.path:shorten_end(a.boundary)
            end
        end
      
        local others = TikzPath:new()
        
        for j, f in pairs(self.edge_list) do
            if j ~= i then
                others:concat(f.path)
            end
        end
        
        e.path_segments = e.path:split_along(others)
    end
end

function Graph:get_best_segments()
    self:find_segments()

    local bad = {}
    
    for _, e in pairs(self.edge_list) do
        for _, s in ipairs(e.path_segments) do
            table.insert(bad, s:at_time(0))
            table.insert(bad, s:at_time(1))
        end
    end
    
    local function dist_to_bad(p)
        local r = 1e9
        
        for _, q in ipairs(bad) do
            r = math.min(r, (p - q):len())
        end
        
        return r
    end
    
    for _, e in pairs(self.edge_list) do
        local best = 0
        
        for _, s in ipairs(e.path_segments) do
            local mid_time = s:mid_time()
            local center = s:at_time(mid_time)
            local d = dist_to_bad(center)
            
            if d > best then
                best = d
                e.label_segment = s
                e.label_anchor = center
                e.label_normal = s:normal_at_time(mid_time)
            end
        end
    end
end

function Graph:place_labels()
    -- In a first step, we identify the "best" segment on each edge to put a
    -- label on, i.e. the one whose center maximizes the distance to all
    -- intersections
    self:get_best_segments()
    
    -- Now we orient normals in a way that attempts to maximize the distances
    -- between the different labels
    local anchors = {}
    
    local function myround(x)
        local function round_to_zero(x)
            if x < 0 then
                return math.ceil(x)
            else
                return math.floor(x)
            end
        end
    
        local S = math.pi / 4
        
        if x < 0 then
            return math.ceil((x - S/2)/S)*S
        else
            return math.floor((x + S/2)/S)*S
        end
    end
    
    local function round_dir(v)
        local alpha = myround(v:angle())
        return Vector:new(math.cos(alpha), math.sin(alpha))
    end

    for i, e in pairs(self.edge_list) do
        if self.args.follow_edges then
            e.anchor_normal = e.label_normal
        else
            e.anchor_normal = 5 * round_dir(e.label_normal)
        end
        
        anchors[i] = {left = e.label_anchor + e.anchor_normal,
                      right = e.label_anchor - e.anchor_normal}
    end
    
    local function dist_to_others(p, curr)
        local r = 1e9
        
        for i, q in ipairs(anchors) do
            if i ~= curr then
                r = math.min(r, (p - q.left):len())
                r = math.min(r, (p - q.right):len())
            end
        end
        
        return r
    end
    
    for i, e in pairs(self.edge_list) do
        if not e.fixed_normal then
            local d1 = dist_to_others(anchors[i].left, i)
            local d2 = dist_to_others(anchors[i].right, i)
                
            if math.abs(d1 - d2) < .01 then
                -- If our heuristic is inconclusive, we instead use a
                -- "symmetric" strategy: if we have a chain of edges lying on 
                -- the same line we want all labels on the same side, regardless
                -- of orientation of the individual edges                
                if math.abs(e.anchor_normal.x) < .01 then
                    if e.anchor_normal.y > 0 then
                        e.anchor_normal = -e.anchor_normal
                    end
                elseif e.anchor_normal.x > 0 then
                    e.anchor_normal = -e.anchor_normal
                end
                        
            elseif d1 < d2 then
                e.anchor_normal = -e.anchor_normal
            end
        end
        
        local alpha = e.anchor_normal:angle()  
        local theta = alpha * 180 / math.pi
                
        if self.args.follow_edges then
            local phi = (theta - 90) % 360

            local eps = 2.5
                        
            if phi > 90 + eps and phi < 270 - eps then
                phi = phi + 180
            end
                        
            local off = 2.5 - 2 * math.min(math.abs(math.sin(alpha)),
                                  math.abs(math.cos(alpha)))
                    
            tex.print("\\draw node[label={[centered,rotate=" ..
                      string.format("%0.5f", phi) .. 
                      ",transform shape,inner sep=0pt,fill=white]" ..
                      string.format("%0.5f", theta) .. ":" .. e.label .. 
                      "}] at " .. (e.label_anchor + 
                                   off * e.anchor_normal):tikz_repr() ..
                      " {};")
                    

        else                    
            -- For my feeling, TikZ positions labels too far away for lines that
            -- aren't axis parallel; we fix this by setting label distance
            -- appropriately
            local off = -1.5 - 2.5 * math.min(math.abs(math.sin(alpha)),
                                              math.abs(math.cos(alpha)))
            
            tex.print("\\draw node[label={[inner sep=0pt,label distance=" ..
                      string.format("%0.3f", off) .. "pt,fill=white]" ..
                      tostring(theta) .. ":" .. e.label .. "}] at " ..
                      e.label_anchor:tikz_repr() .. " {};")
        end
    end
end

function Graph:select_instance(x)
    if x ~= nil then
        return Graph.instances[x]
    else
        return Graph.instances[Graph.curr_instance]
    end
end
