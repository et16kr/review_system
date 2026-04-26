"use server";
export async function save(formData) { const name = formData.get("name"); return name; }
