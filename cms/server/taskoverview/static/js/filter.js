function _has_tag(info, tag) {
  for (const col of ["keywords", "tags"]) {
    if ((info[col] || []).some((c) => c.toUpperCase() === tag.toUpperCase()))
      return true;
  }
  return false;
}

function compile_expr(expr) {
  if (!expr || !expr.trim())
    return null;
  try {
    const js = expr.replace(/["']([^"']+)["']/g, (_, tag) => `__has(info,"${tag}")`);
    const fn = new Function("info", "__has", `"use strict"; return !!(${js});`);
    fn({ tags: [], keywords: [] }, _has_tag); // run once to catch errors
    return (info) => fn(info, _has_tag);
  } catch(e) {
    return null;
  }
}

function _relevant(task, criteria, fn) {
  const info = window.__info[task];
  if (!!info["error"])
    return true;
  for(var i = 0; i < info.uses.length; ++i)
    if(info.uses[i].timestamp > criteria.only_before)
      return false;
  if (info.algorithm > criteria.alg_diff.upper || criteria.alg_diff.lower > info.algorithm)
    return false;
  if (info.implementation > criteria.impl_diff.upper || criteria.impl_diff.lower > info.implementation)
    return false;

  if (fn !== null) {
    try {
      const res = fn(info)
      return res;
    } catch (e) {
      console.error("failed to filter", e);
      // fallback to standard filter
    }
  }
  for (const col of ["keywords", "tags"]) {
    for (const v of criteria[col] || [])
      if (!(info[col] || []).some((c) => c.toUpperCase() === v.toUpperCase()))
        return false;
  }
  return true;
}