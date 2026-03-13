/* document.addEventListener("DOMContentLoaded", function () {

  const reveals = document.querySelectorAll(".reveal");

  window.addEventListener("scroll", function () {

    reveals.forEach(function(element){

      const windowHeight = window.innerHeight;
      const elementTop = element.getBoundingClientRect().top;
      const visiblePoint = 100;

      if(elementTop < windowHeight - visiblePoint){
        element.classList.add("active");
      }

    });

  });

});

*/

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {

    if(entry.isIntersecting){
      entry.target.classList.add("active");
      observer.unobserve(entry.target);
    }

  });
},{
  threshold: 0.15
});

document.querySelectorAll(".reveal").forEach(el => {
  observer.observe(el);
});

// CALENDARIO

const button = document.getElementById("open-calendar");
const calendar = document.getElementById("calendar");

if(button && calendar){

button.addEventListener("click", function(){

calendar.classList.toggle("active");

});

}