"use server";
export async function save(formData: FormData) { const name = formData.get("name"); return name; }
