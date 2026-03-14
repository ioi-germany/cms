const { computed, inject, provide, ref, toRefs } = Vue

var __color_map = new Map();
const PUBLIC_TAG = "PUBLIC";
const PRIVATE_TAG = "PRIVATE";

const GOLDEN_RATIO = 1.618033988749895;
function get_color(tag) {
  if (!window.__color_map.has(tag)) {
    const h = (window.__color_map.size * 360/GOLDEN_RATIO) % 360;
    window.__color_map.set(tag, { h, s: 100, l: 85});
  }
  return window.__color_map.get(tag);
}

const Pill = {
  delimiters: ["[[", "]]"],
  emits: ["filter-tag"],
  props: ["filters", "tag"],
  template: "#pill",
  setup(props, ctx) {
    const { filters, tag } = toRefs(props);
    const is_filtered = computed(() => filters.value?.has(tag.value));

    function toggle_filter() {
      ctx.emit("filter-tag", tag.value);
    }

    const color = computed(() => window.get_color(tag.value));
    const background = computed(() => {
      const { h, s, l } = color.value;
      if (is_filtered.value)
        return `hsl(${h}, ${s}%, 40%)`;
      else
        return `hsl(${h}, ${s}%, ${l}%)`;
    });

    return {
      background,
      toggle_filter,
      filtered: is_filtered
    };
  }
};

const Cell = {
  delimiters: ["[[", "]]"],
  components: { Pill },
  props: ["col", "criteria", "info"],
  template: "#cell",
  setup(props, ctx) {
    const { col, criteria, info } = toRefs(props);
    const { update_criteria } = inject("criteria");

    function update_filter(args) {
      update_criteria({ [col.value.id]: args });
    }

    return { 
      data: info.value[col.value.id],
      filters: criteria.value?.[col.value.id], 
      update_filter 
    };
  }
};

const OverviewTable = {
  delimiters: ["[[", "]]"],
  components: { Cell },
  setup() {
    const tasks = ref([]);
    const show_col = ref(window.entries.reduce((acc, e) => {
      acc[e] = true;
      return acc;
    }, {}));
    const criteria = ref({ 
      alg_diff: { lower: 0, upper: 10 },
      impl_diff: { lower: 0, upper: 10 },
      only_before: Infinity
    });
    const is_new = ref({});
    const is_updated = ref({});

    function _relevant(task, criteria) {
      const info = window.__info[task];
      if("error" in info)
        return true;
      for(var i = 0; i < info.uses.length; ++i)
          if(info.uses[i].timestamp > criteria.only_before)
              return false;
      if (info.algorithm > criteria.alg_diff.upper || criteria.alg_diff.lower > info.algorithm)
        return false;
      if (info.implementation > criteria.impl_diff.upper || criteria.impl_diff.lower > info.implementation)
        return false;
      for (const col of ["keywords", "tags"]) {
        for (const v of criteria[col] || []) {
          if (!(info[col] || []).some((c) => c.toUpperCase() === v.toUpperCase()))
            return false;
        }
      }
      return true;
    }

    function _updateTaskRows(new_tasks, updated_tasks, removed_tasks, _show_col, _criteria, init) {
      if (_criteria !== null) {
        const tags = criteria.value.tags ?? new Set();
        if (_criteria.tags) {
          for (const t of [PUBLIC_TAG, PRIVATE_TAG])
            tags.delete(t);
          for (const t of _criteria.tags)
            tags.add(t);
        }
        criteria.value = { ...criteria.value, ..._criteria, tags };
      }
      if (_show_col !== null)
        show_col.value = { ..._show_col };
      if (Object.keys(removed_tasks).length > 0) {
        tasks.value = tasks.value.filter((t) => !(t in removed_tasks));
      }
      if (updated_tasks.length > 0) {
        // trigger update
        tasks.value = [ ...tasks.value ];
        updated_tasks.forEach((t) => {
          is_updated.value[t] = true;
        });
        setTimeout(() => {
          updated_tasks.forEach((t) => {
            is_updated.value[t] = false;
          });
        }, 1000);
      }
      if (new_tasks.length > 0) {
        tasks.value = tasks.value.concat(new_tasks)
          .sort((ta,tb) => ta.localeCompare(tb));
        if (!init) {
          new_tasks.forEach((t) => {
            is_new.value[t] = true;
          });
          setTimeout(() => {
            new_tasks.forEach((t) => {
              is_new.value[t] = false;
            });
          }, 1000);
        }
      }
    }

    function update_criteria(arg) {
      for (const [k, v] of Object.entries(arg)) {
        if (criteria.value[k]?.has(v))
          criteria.value[k].delete(v);
        else {
          if (!(k in criteria.value))
            criteria.value[k] = new Set();
          criteria.value[k].add(v);
        }
      }
      // symc with the modal
      window.criteria.tags = criteria.value.tags;
    }

    provide("criteria", { update_criteria });

    let json_issues = computed(() => tasks.value.filter((t) => "error" in window.__info[t]));
    const relevant_tasks = computed(() => {
      let i = -1;
      return tasks.value.map((t) => {
        const hidden = !_relevant(t, criteria.value);
        if (!hidden)
          i++;
        return {
          id: t,
          info: window.__info[t],
          is_updated: is_updated.value[t],
          is_new: is_new.value[t],
          hidden,
          odd: i % 2 == 1
        };
      });
    });
    const columns = computed(() => window.entries
      .filter((e) => show_col.value[e])
      .map((e) => ({ id: e, desc: window.desc[e] }))
    );
    const num_interesting_columns = computed(() => window.entries
      .slice(1, -1)
      .filter((e) => show_col.value[e])
      .length
    );
    window.updateTaskRows = _updateTaskRows;

    return {
      columns,
      criteria,
      num_interesting_columns,
      json_issues,
      tasks: relevant_tasks
    };
  }
}