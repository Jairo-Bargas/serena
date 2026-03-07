document.addEventListener("DOMContentLoaded", function () {

  const hero = document.querySelector(".hero");

  window.addEventListener("scroll", function () {

    let scroll = window.scrollY;

    hero.style.backgroundPositionY = scroll * 0.5 + "px";

  });

});