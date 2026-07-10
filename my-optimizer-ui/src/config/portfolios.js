import {supabase} from "./supabaseClient.js";

export async function savePortfolio(name, type, inputs, results){
    const {data : {user}} = await supabase.auth.getUser();
    if (!user){
        throw new Error("You must be logged in to save.");
    }
    const {data, error} = await supabase.from("portfolios").insert({name, type, inputs, results, user_id : user.id}).select().single();
    if (error){
        throw error;
    }
    return data;
}   

export async function listPortfolios(){
    const {data, error} = await supabase.from("portfolios").select().order("created_at", {ascending : false});
    if (error){
        throw error;
    }
    return data;
}

export async function deletePortfolio(id){
    const {error} = await supabase.from("portfolios").delete().eq("id", id);
    if (error){
        throw error;
    }
}