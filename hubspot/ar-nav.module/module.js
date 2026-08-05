(function () {
  function boot() {
    var nav = document.querySelector(".ar-nav");
    if (!nav) return;
    var links = nav.querySelectorAll(".ar-nav-link");
    var map = {};
    for (var i = 0; i < links.length; i++) {
      var id = (links[i].getAttribute("href") || "").replace(/^#/, "");
      if (id) map[id] = links[i];
    }
    var targets = Object.keys(map)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);
    if (!("IntersectionObserver" in window) || !targets.length) return;

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          for (var i = 0; i < links.length; i++) links[i].classList.remove("active");
          var link = map[e.target.id];
          if (link) link.classList.add("active");
        }
      });
    }, { rootMargin: "-40% 0px -55% 0px" });

    targets.forEach(function (t) { io.observe(t); });
  }
  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
