/*! Native CLI for preview JSON and print packs, using the browser's exact engine.
Batch mode reads one JSON request per line for independent compatibility checks. */
use relief_core::{EngineError, Result, artwork, exports, geometry, settings::Settings};
use serde_json::{Value, json};
use std::io::{self, BufRead, Write};
fn run(request: Value) -> Result<Value> {
    let data = if let Some(path) = request["input"].as_str() {
        std::fs::read(path).map_err(|e| EngineError::input(e.to_string()))?
    } else {
        artwork::SAMPLE.to_vec()
    };
    let settings = Settings::parse(
        &request
            .get("settings")
            .cloned()
            .unwrap_or(json!({}))
            .to_string(),
    )?;
    let project = geometry::build(&data, settings)?;
    if let Some(path) = request["output"].as_str() {
        let pack = exports::export(&project)?;
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .map_err(|e| EngineError::input(format!("Choose a new output file: {e}")))?;
        if let Err(error) = file.write_all(&pack.pack) {
            let _ = std::fs::remove_file(path);
            return Err(EngineError::input(error.to_string()));
        }
    }
    if request["preview"] == true {
        return exports::preview(&project, "native");
    }
    Ok(
        json!({"manifest":exports::manifest(&project)?,"artwork":{"area":project.vector.area(),"bounds":artwork::bounds(&project.vector),"regions":project.vector.decompose().len(),"holes":project.vector.to_polygons().iter().filter(|r|artwork::signed_area(r)<0.0).count()}}),
    )
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    if args.get(1).is_some_and(|s| s == "--batch") {
        for line in io::stdin().lock().lines() {
            let result = line
                .map_err(|e| EngineError::input(e.to_string()))
                .and_then(|line| {
                    serde_json::from_str(&line).map_err(|e| EngineError::input(e.to_string()))
                })
                .and_then(run);
            println!(
                "{}",
                match result {
                    Ok(v) => v,
                    Err(e) => json!({"error":e}),
                }
            );
        }
        return;
    }
    let mut request = json!({});
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--input" | "--settings" | "--output" if i + 1 < args.len() => {
                let key = args[i].trim_start_matches('-');
                i += 1;
                if key == "settings" {
                    request[key] = serde_json::from_slice(
                        &std::fs::read(&args[i]).expect("Read settings file"),
                    )
                    .expect("Settings JSON");
                } else {
                    request[key] = json!(args[i]);
                }
            }
            "--preview" => request["preview"] = json!(true),
            "--defaults" => {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&Settings::parse("{}").unwrap()).unwrap()
                );
                return;
            }
            _ => {
                eprintln!(
                    "Usage: relief-native [--input IMAGE] [--settings JSON] [--output PACK.zip] [--preview | --defaults | --batch]"
                );
                std::process::exit(2);
            }
        }
        i += 1;
    }
    match run(request) {
        Ok(v) => println!("{}", v),
        Err(e) => {
            eprintln!("{}", json!(e));
            std::process::exit(1);
        }
    }
}
