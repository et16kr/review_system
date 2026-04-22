export function render(html) {
  document.write(html);
  setTimeout("render('done')", 100);
}
